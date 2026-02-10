"""
Unified GitHub Connection Service.

This service provides a unified interface for both GitHub OAuth and GitHub App
integrations, allowing users to connect repositories through either method
based on their needs and permissions.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Union
from enum import Enum

from logconfig.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.user import User, GitHubConnection
from app.services.github_service import GitHubIntegrationService
from app.services.github_app_service import GitHubAppService
from app.schemas.github import (
    GitHubRepository,
    GitHubConnectionStatus,
    GitHubSyncResponse,
    GitHubInstallation
)

logger = get_logger()


class GitHubConnectionType(str, Enum):
    """GitHub connection types."""
    OAUTH = "oauth"
    APP = "app"
    HYBRID = "hybrid"  # Both OAuth and App connected


class GitHubConnectionService:
    """
    Unified service for managing GitHub connections.
    
    This service provides a single interface for both OAuth and GitHub App
    integrations, automatically choosing the best method for each operation.
    """

    def __init__(self):
        """Initialize the unified GitHub connection service."""
        self.oauth_service = GitHubIntegrationService()
        self.app_service = GitHubAppService()

    async def get_connection_options(
        self, db: AsyncSession, user: User
    ) -> Dict[str, Any]:
        """
        Get available GitHub connection options for a user.
        
        Args:
            db: Database session
            user: User object
            
        Returns:
            Dictionary with connection options and status
        """
        try:
            # Get existing connections
            result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.user_id == user.id,
                    GitHubConnection.is_active == True
                )
            )
            connections = result.scalars().all()
            
            oauth_connected = any(conn.is_github_oauth_connected for conn in connections)
            app_connected = any(conn.is_github_app_connected for conn in connections)
            
            # Determine connection type
            if oauth_connected and app_connected:
                connection_type = GitHubConnectionType.HYBRID
            elif oauth_connected:
                connection_type = GitHubConnectionType.OAUTH
            elif app_connected:
                connection_type = GitHubConnectionType.APP
            else:
                connection_type = None
            
            return {
                "connection_type": connection_type,
                "oauth_connected": oauth_connected,
                "app_connected": app_connected,
                "oauth_available": True,  # OAuth is always available
                "app_available": self.app_service.is_configured(),
                "recommendations": self._get_connection_recommendations(
                    oauth_connected, app_connected
                )
            }
            
        except Exception as e:
            logger.error(f"Error getting connection options for user {user.id}: {str(e)}")
            raise

    def _get_connection_recommendations(
        self, oauth_connected: bool, app_connected: bool
    ) -> Dict[str, str]:
        """Get connection recommendations based on current status."""
        if not oauth_connected and not app_connected:
            return {
                "primary": "Start with GitHub OAuth for personal repositories",
                "secondary": "Add GitHub App for organization repositories later",
                "use_case": "oauth_first"
            }
        elif oauth_connected and not app_connected:
            return {
                "primary": "Your personal repositories are connected via OAuth",
                "secondary": "Add GitHub App to access organization repositories",
                "use_case": "add_app"
            }
        elif not oauth_connected and app_connected:
            return {
                "primary": "Organization repositories connected via GitHub App",
                "secondary": "Add OAuth for personal repository access",
                "use_case": "add_oauth"
            }
        else:
            return {
                "primary": "Full GitHub integration active",
                "secondary": "You have access to both personal and organization repositories",
                "use_case": "complete"
            }

    async def connect_oauth(
        self, db: AsyncSession, user: User, code: str
    ) -> Dict[str, Any]:
        """
        Connect GitHub OAuth for a user.
        
        Args:
            db: Database session
            user: User object
            code: OAuth authorization code
            
        Returns:
            Connection result with user profile
        """
        try:
            logger.info(f"Connecting GitHub OAuth for user: {user.id}")
            
            # Use existing OAuth service
            github_profile = await self.oauth_service.exchange_code_for_token(
                db, user, code
            )
            
            return {
                "success": True,
                "connection_type": "oauth",
                "github_profile": {
                    "id": github_profile.id,
                    "login": github_profile.login,
                    "name": getattr(github_profile, 'name', None),
                    "email": getattr(github_profile, 'email', None),
                    "avatar_url": getattr(github_profile, 'avatar_url', None)
                },
                "message": "GitHub OAuth connected successfully"
            }
            
        except Exception as e:
            logger.error(f"Error connecting OAuth for user {user.id}: {str(e)}")
            raise

    async def connect_app_installation(
        self, db: AsyncSession, user: User, installation_id: int
    ) -> Dict[str, Any]:
        """
        Connect GitHub App installation for a user.
        
        Args:
            db: Database session
            user: User object
            installation_id: GitHub App installation ID
            
        Returns:
            Connection result with installation details
        """
        try:
            logger.info(f"Connecting GitHub App installation {installation_id} for user: {user.id}")
            
            # Get or create GitHub connection record
            result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.user_id == user.id
                )
            )
            github_connection = result.scalars().first()

            if not github_connection:
                github_connection = GitHubConnection(user_id=user.id)
                db.add(github_connection)

            # Connect GitHub App
            github_connection.connect_github_app(
                installation_id=installation_id,
                app_id=int(self.app_service.app_id)
            )

            await db.commit()
            await db.refresh(github_connection)
            
            return {
                "success": True,
                "connection_type": "app",
                "installation_id": installation_id,
                "app_id": self.app_service.app_id,
                "message": "GitHub App installation connected successfully"
            }
            
        except Exception as e:
            logger.error(f"Error connecting App installation for user {user.id}: {str(e)}")
            await db.rollback()
            raise

    async def get_available_repositories(
        self, db: AsyncSession, user: User, connection_type: Optional[str] = None
    ) -> Dict[str, List[GitHubRepository]]:
        """
        Get all available repositories from connected GitHub integrations.
        
        Args:
            db: Database session
            user: User object
            connection_type: Optional filter by connection type ('oauth', 'app', or None for all)
            
        Returns:
            Dictionary with repositories grouped by source
        """
        try:
            repositories = {
                "oauth_repos": [],
                "app_repos": [],
                "total_count": 0
            }
            
            # Get GitHub connections
            result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.user_id == user.id,
                    GitHubConnection.is_active == True
                )
            )
            connections = result.scalars().all()
            
            # Get OAuth repositories
            if connection_type in [None, "oauth"]:
                oauth_connection = next(
                    (conn for conn in connections if conn.is_github_oauth_connected), None
                )
                if oauth_connection:
                    try:
                        oauth_repos = await self.oauth_service.get_user_repositories(db, user)
                        repositories["oauth_repos"] = oauth_repos
                        logger.info(f"Retrieved {len(oauth_repos)} OAuth repositories")
                    except Exception as e:
                        logger.warning(f"Failed to get OAuth repositories: {str(e)}")
            
            # Get App repositories
            if connection_type in [None, "app"]:
                app_connection = next(
                    (conn for conn in connections if conn.is_github_app_connected), None
                )
                if app_connection and app_connection.github_installation_id:
                    try:
                        # Get repositories accessible through the installation
                        app_repos = await self._get_app_repositories(
                            app_connection.github_installation_id
                        )
                        repositories["app_repos"] = app_repos
                        logger.info(f"Retrieved {len(app_repos)} App repositories")
                    except Exception as e:
                        logger.warning(f"Failed to get App repositories: {str(e)}")
            
            repositories["total_count"] = len(repositories["oauth_repos"]) + len(repositories["app_repos"])
            
            return repositories
            
        except Exception as e:
            logger.error(f"Error getting repositories for user {user.id}: {str(e)}")
            raise

    async def sync_to_repository(
        self,
        db: AsyncSession,
        user: User,
        repository_full_name: str,
        files_content: Dict[str, str],
        commit_message: str,
        branch: str = "main",
        preferred_method: Optional[str] = None
    ) -> GitHubSyncResponse:
        """
        Sync files to a repository using the best available method.
        
        Args:
            db: Database session
            user: User object
            repository_full_name: Target repository (owner/repo)
            files_content: Dictionary of file paths to content
            commit_message: Commit message
            branch: Target branch
            preferred_method: Preferred sync method ('oauth' or 'app')
            
        Returns:
            GitHubSyncResponse with sync results
        """
        try:
            logger.info(f"Syncing to repository {repository_full_name} for user: {user.id}")
            
            # Get available connections
            result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.user_id == user.id,
                    GitHubConnection.is_active == True
                )
            )
            connections = result.scalars().all()
            
            oauth_connection = next(
                (conn for conn in connections if conn.is_github_oauth_connected), None
            )
            app_connection = next(
                (conn for conn in connections if conn.is_github_app_connected), None
            )
            
            # Determine sync method
            sync_method = await self._determine_sync_method(
                repository_full_name, oauth_connection, app_connection, preferred_method
            )
            
            if sync_method == "oauth" and oauth_connection:
                return await self._sync_via_oauth(
                    db, user, repository_full_name, files_content, commit_message, branch
                )
            elif sync_method == "app" and app_connection:
                return await self._sync_via_app(
                    db, user, app_connection.github_installation_id,
                    repository_full_name, files_content, commit_message, branch
                )
            else:
                raise ValueError(f"No suitable GitHub connection available for repository {repository_full_name}")
                
        except Exception as e:
            logger.error(f"Error syncing to repository {repository_full_name}: {str(e)}")
            raise

    async def _determine_sync_method(
        self,
        repository_full_name: str,
        oauth_connection: Optional[GitHubConnection],
        app_connection: Optional[GitHubConnection],
        preferred_method: Optional[str]
    ) -> str:
        """Determine the best sync method for a repository."""
        
        # If user has a preference and the connection is available, use it
        if preferred_method == "oauth" and oauth_connection:
            return "oauth"
        elif preferred_method == "app" and app_connection:
            return "app"
        
        # Auto-determine based on repository and available connections
        owner, repo = repository_full_name.split("/", 1)
        
        # If both are available, prefer App for organizations, OAuth for personal
        if oauth_connection and app_connection:
            # Try to determine if it's an organization repo
            # This is a heuristic - in practice, you might want to check the actual repo
            if oauth_connection.github_username and owner.lower() != oauth_connection.github_username.lower():
                return "app"  # Likely an organization repo
            else:
                return "oauth"  # Likely a personal repo
        
        # Use whatever is available
        if oauth_connection:
            return "oauth"
        elif app_connection:
            return "app"
        
        raise ValueError("No GitHub connection available")

    async def _sync_via_oauth(
        self,
        db: AsyncSession,
        user: User,
        repository_full_name: str,
        files_content: Dict[str, str],
        commit_message: str,
        branch: str
    ) -> GitHubSyncResponse:
        """Sync files using OAuth connection."""
        return await self.oauth_service.sync_project_to_repository(
            db=db,
            user=user,
            project_id="",  # This might need to be passed as parameter
            repository_full_name=repository_full_name,
            files_content=files_content,
            commit_message=commit_message,
            branch=branch
        )

    async def _sync_via_app(
        self,
        db: AsyncSession,
        user: User,
        installation_id: int,
        repository_full_name: str,
        files_content: Dict[str, str],
        commit_message: str,
        branch: str
    ) -> GitHubSyncResponse:
        """Sync files using GitHub App connection."""
        owner, repo = repository_full_name.split("/", 1)
        
        sync_result = await self.app_service.sync_repository(
            installation_id=installation_id,
            repo_owner=owner,
            repo_name=repo,
            files=files_content,
            commit_message=commit_message,
            branch=branch
        )
        
        # Convert to GitHubSyncResponse format
        return GitHubSyncResponse(
            sync_id=f"app_{installation_id}_{sync_result['commit_sha'][:8]}",
            status="completed" if sync_result["success"] else "failed",
            repository_full_name=repository_full_name,
            branch=branch,
            commit_sha=sync_result["commit_sha"],
            commit_url=sync_result["commit_url"],
            files_synced=sync_result["files_synced"],
            error_message=None if sync_result["success"] else "Sync failed",
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )

    async def _get_app_repositories(self, installation_id: int) -> List[GitHubRepository]:
        """Get repositories accessible through GitHub App installation."""
        try:
            # Get installation access token
            access_token = await self.app_service.get_installation_access_token(installation_id)
            
            # Get repositories for this installation
            url = f"{self.app_service.api_base_url}/installation/repositories"
            headers = {
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            response = await self.app_service.http_client.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                repositories = []
                
                for repo_data in data.get("repositories", []):
                    repository = GitHubRepository(
                        id=repo_data["id"],
                        name=repo_data["name"],
                        full_name=repo_data["full_name"],
                        description=repo_data.get("description"),
                        private=repo_data["private"],
                        html_url=repo_data["html_url"],
                        clone_url=repo_data["clone_url"],
                        created_at=datetime.fromisoformat(repo_data["created_at"].replace("Z", "+00:00")),
                        updated_at=datetime.fromisoformat(repo_data["updated_at"].replace("Z", "+00:00"))
                    )
                    repositories.append(repository)
                
                return repositories
            else:
                logger.error(f"Failed to get installation repositories: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting App repositories for installation {installation_id}: {str(e)}")
            return []

    async def disconnect_github(
        self, db: AsyncSession, user: User, connection_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Disconnect GitHub integrations.
        
        Args:
            db: Database session
            user: User object
            connection_type: Type to disconnect ('oauth', 'app', or None for all)
            
        Returns:
            Disconnection results
        """
        try:
            results = {
                "oauth_disconnected": False,
                "app_disconnected": False,
                "errors": []
            }
            
            # Get GitHub connections
            result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.user_id == user.id,
                    GitHubConnection.is_active == True
                )
            )
            connections = result.scalars().all()
            
            for connection in connections:
                try:
                    if connection_type in [None, "oauth"] and connection.is_github_oauth_connected:
                        connection.disconnect_github_oauth()
                        results["oauth_disconnected"] = True
                        logger.info(f"Disconnected OAuth for user: {user.id}")
                    
                    if connection_type in [None, "app"] and connection.is_github_app_connected:
                        connection.disconnect_github_app()
                        results["app_disconnected"] = True
                        logger.info(f"Disconnected App for user: {user.id}")
                        
                except Exception as e:
                    error_msg = f"Failed to disconnect {connection.connection_type}: {str(e)}"
                    results["errors"].append(error_msg)
                    logger.error(error_msg)
            
            await db.commit()
            return results
            
        except Exception as e:
            logger.error(f"Error disconnecting GitHub for user {user.id}: {str(e)}")
            await db.rollback()
            raise

    async def get_unified_status(
        self, db: AsyncSession, user: User
    ) -> Dict[str, Any]:
        """
        Get unified GitHub connection status.
        
        Args:
            db: Database session
            user: User object
            
        Returns:
            Comprehensive connection status
        """
        try:
            # Get connection options
            options = await self.get_connection_options(db, user)
            
            # Get OAuth status if connected
            oauth_status = None
            if options["oauth_connected"]:
                try:
                    oauth_status = await self.oauth_service.get_connection_status(db, user)
                except Exception as e:
                    logger.warning(f"Failed to get OAuth status: {str(e)}")
            
            # Get App installations if connected
            app_installations = []
            if options["app_connected"]:
                try:
                    # This would require user's OAuth token to list installations
                    # For now, we'll just indicate that App is connected
                    pass
                except Exception as e:
                    logger.warning(f"Failed to get App installations: {str(e)}")
            
            return {
                "connection_type": options["connection_type"],
                "oauth": {
                    "connected": options["oauth_connected"],
                    "status": oauth_status
                },
                "app": {
                    "connected": options["app_connected"],
                    "installations": app_installations
                },
                "capabilities": {
                    "can_access_personal_repos": options["oauth_connected"],
                    "can_access_org_repos": options["app_connected"],
                    "can_push_code": options["oauth_connected"] or options["app_connected"],
                    "can_pull_code": options["oauth_connected"] or options["app_connected"]
                },
                "recommendations": options["recommendations"]
            }
            
        except Exception as e:
            logger.error(f"Error getting unified status for user {user.id}: {str(e)}")
            raise