"""
GitHub App OAuth Service - Simplified App-only integration.

This service uses GitHub App's OAuth flow to automatically handle installation
mapping without requiring webhooks or manual installation IDs.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import time
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import jwt
import httpx
from logconfig.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.settings import get_settings
from app.models.user import GitHubConnection
from app.dependencies.auth import CurrentUser
from app.schemas.github import GitHubRepository

logger = get_logger()
settings = get_settings()


class GitHubAppOAuthService:
    """
    Simplified GitHub App service using OAuth flow for automatic installation mapping.
    
    This eliminates the need for webhooks and manual installation ID management.
    """

    def __init__(self):
        """Initialize the GitHub App OAuth service."""
        self.app_id = settings.GITHUB_APP_ID
        self.client_id = settings.GITHUB_CLIENT_ID  # App's client ID
        self.client_secret = settings.GITHUB_CLIENT_SECRET  # App's client secret
        self.private_key = settings.GITHUB_PRIVATE_KEY
        
        # GitHub API base URL
        self.api_base_url = "https://api.github.com"
        
        # HTTP client for API requests
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "InfraJet-GitHub-App/1.0"
            }
        )
        
        self._validate_configuration()

    def _validate_configuration(self) -> None:
        """Validate GitHub App configuration."""
        missing_configs = []
        
        if not self.app_id or self.app_id == "your-app-id-here":
            missing_configs.append("GITHUB_APP_ID")
        
        if not self.client_id or self.client_id == "your-client-id-here":
            missing_configs.append("GITHUB_CLIENT_ID")
        
        if not self.client_secret or self.client_secret == "your-client-secret-here":
            missing_configs.append("GITHUB_CLIENT_SECRET")
        
        if not self.private_key or self.private_key == "your-github-app-private-key-here":
            missing_configs.append("GITHUB_PRIVATE_KEY")
        
        if missing_configs:
            raise ValueError(f"GitHub App configuration incomplete. Missing: {', '.join(missing_configs)}")

    def is_configured(self) -> bool:
        """Check if GitHub App is properly configured."""
        try:
            self._validate_configuration()
            return True
        except ValueError:
            return False

    def generate_jwt_token(self) -> str:
        """Generate GitHub App JWT token for authentication."""
        if not self.app_id or not self.private_key:
            raise ValueError("GitHub App ID and private key are required")
        
        try:
            # JWT payload
            now = int(time.time())
            payload = {
                "iat": now - 60,  # Issued at time (60 seconds ago to account for clock skew)
                "exp": now + (10 * 60),  # Expires in 10 minutes
                "iss": self.app_id  # Issuer (GitHub App ID)
            }
            
            # Handle different private key formats
            private_key = self.private_key
            
            if private_key.startswith("-----BEGIN"):
                # Already in PEM format
                pass
            else:
                # Try to decode from base64
                try:
                    private_key = base64.b64decode(private_key).decode('utf-8')
                except Exception:
                    # If decoding fails, use as-is
                    pass
            
            # Generate JWT token
            token = jwt.encode(payload, private_key, algorithm="RS256")
            return token
            
        except Exception as e:
            logger.error(f"Failed to generate GitHub App JWT token: {str(e)}")
            raise ValueError(f"Failed to generate JWT token: {str(e)}")

    # async def get_authorization_url(self, user_id: str, state: Optional[str] = None) -> Tuple[str, str]:
    #     """
    #     Get GitHub App OAuth authorization URL.

    #     This URL will handle both app installation (if needed) and user authorization.

    #     Args:
    #         user_id: User ID to include in state
    #         state: Optional state parameter for CSRF protection

    #     Returns:
    #         Tuple of (authorization_url, state)
    #     """
    #     if not settings.GITHUB_REDIRECT_URI:
    #         raise ValueError("GITHUB_REDIRECT_URI must be configured for GitHub OAuth to work. Please set it to your frontend callback URL.")

    #     if state is None:
    #         random_part = secrets.token_urlsafe(32)
    #         state = f"{user_id}:{random_part}"

    #     # GitHub App OAuth URL with setup_action=install for combined auth + installation
    #     auth_url = f"https://github.com/login/oauth/authorize?client_id={self.client_id}&scope=repo,user:email,user&state={state}&redirect_uri={settings.GITHUB_REDIRECT_URI}&setup_action=install"

    #     logger.info(f"Generated GitHub App OAuth URL for user {user_id}, state: {state}")
    #     return auth_url, state

    async def get_authorization_url(self, user_id: str, state: Optional[str] = None) -> Tuple[str, str]:
        """
        Get GitHub App installation URL (like Vercel uses).
        This creates a permanent installation without OAuth tokens.
        """
        if state is None:
            random_part = secrets.token_urlsafe(32)
            state = f"{user_id}:{random_part}"

        app_slug = getattr(settings, 'GITHUB_APP_SLUG', None)
        if not app_slug:
            raise ValueError("GITHUB_APP_SLUG must be configured")

        # Direct installation URL - no OAuth involved
        install_url = f"https://github.com/apps/{app_slug}/installations/new?state={state}"

        logger.info(f"Generated GitHub App installation URL for user {user_id}")
        return install_url, state

    def get_install_url(self) -> str:
        """Get GitHub App installation URL."""
        app_slug = getattr(settings, 'GITHUB_APP_SLUG', None)
        if not app_slug:
            raise ValueError("GITHUB_APP_SLUG must be configured. Set it to your GitHub App's slug (e.g., 'my-app-slug').")
        return f"https://github.com/apps/{app_slug}/installations/new"

    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token and installation info.
        
        Args:
            code: Authorization code from GitHub callback
            
        Returns:
            Dictionary with tokens and installation information
        """
        try:
            # Exchange code for access token
            token_url = "https://github.com/login/oauth/access_token"
            token_data = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code
            }
            
            headers = {
                "Accept": "application/json",
                "User-Agent": "InfraJet-GitHub-App/1.0"
            }
            
            # Add detailed logging for request
            logger.info(f"Making token exchange request to: {token_url}")
            logger.info(f"Request data: client_id={self.client_id}, code={code[:10]}..., client_secret=***")
            logger.info(f"Request headers: {headers}")
            
            response = await self.http_client.post(token_url, data=token_data, headers=headers)
            
            # Add detailed logging
            logger.info(f"GitHub token exchange response: Status {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            logger.info(f"Response text: {response.text}")
            
            if response.status_code != 200:
                logger.error(f"Token exchange failed with status {response.status_code}")
                logger.error(f"Response body: {response.text}")
                raise ValueError(f"Token exchange failed: HTTP {response.status_code} - {response.text}")
            
            try:
                token_response = response.json()
                logger.info(f"Parsed token response: {token_response}")
            except Exception as json_error:
                logger.error(f"Failed to parse JSON response: {json_error}")
                logger.error(f"Raw response: {response.text}")
                raise ValueError(f"Invalid JSON response from GitHub: {response.text}")
            
            if "error" in token_response:
                logger.error(f"GitHub returned error: {token_response}")
                error_desc = token_response.get('error_description', token_response.get('error', 'Unknown error'))
                raise ValueError(f"Token exchange error: {error_desc}")

            # For GitHub Apps, scopes are determined by app permissions, not OAuth scopes
            # The scope field may be empty, which is normal for GitHub Apps
            # We'll validate by checking if we can get user info and installations

            access_token = token_response["access_token"]
            
            # Get user information
            user_info = await self._get_user_info(access_token)
            
            # Get user's installations for this app
            installations = await self._get_user_installations(access_token)
            
            return {
                "access_token": access_token,
                "user_info": user_info,
                "installations": installations
            }
            
        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {str(e)}")
            raise

    async def _get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from GitHub."""
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = await self.http_client.get(f"{self.api_base_url}/user", headers=headers)
        
        if response.status_code != 200:
            raise ValueError(f"Failed to get user info: HTTP {response.status_code}")
        
        return response.json()

    async def _get_user_installations(self, access_token: str) -> List[Dict[str, Any]]:
        """Get user's installations for this app."""
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = await self.http_client.get(f"{self.api_base_url}/user/installations", headers=headers)
        
        if response.status_code != 200:
            logger.warning(f"Failed to get user installations: HTTP {response.status_code}")
            return []
        
        data = response.json()

        logger.info(f"Found {len(data.get('installations', []))} total installations for user")
        for inst in data.get("installations", []):
            logger.info(f"Installation: app_id={inst.get('app_id')}, id={inst.get('id')}, account={inst.get('account', {}).get('login')}")

        # Filter installations for this app
        app_installations = []
        for installation in data.get("installations", []):
            if installation.get("app_id") == int(self.app_id):
                app_installations.append(installation)

        logger.info(f"Filtered to {len(app_installations)} installations for app_id {self.app_id}")
        return app_installations

    async def connect_user_github(
        self, db: AsyncSession, user: CurrentUser, code: str
    ) -> Dict[str, Any]:
        """
        Connect GitHub App for a user using OAuth flow.
        
        Args:
            db: Database session
            user: User object
            code: Authorization code from GitHub callback
            
        Returns:
            Connection result with user and installation info
        """
        try:
            logger.info(f"Connecting GitHub App for user: {user.id}")
            
            # Exchange code for tokens and info
            token_data = await self.exchange_code_for_tokens(code)
            
            access_token = token_data["access_token"]
            user_info = token_data["user_info"]
            installations = token_data["installations"]
            
            # Get or create GitHub connection record
            result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.supabase_user_id == user.supabase_user_id
                )
            )
            github_connection = result.scalars().first()

            if not github_connection:
                github_connection = GitHubConnection(supabase_user_id=user.supabase_user_id)
                db.add(github_connection)

            # Connect GitHub account
            installation_id = installations[0]["id"] if installations else None
            github_connection.connect_github(
                github_user_id=user_info["id"],
                github_username=user_info["login"],
                access_token=self._encrypt_token(access_token),
                installation_id=installation_id
            )
            
            if installation_id:
                logger.info(f"Connected installation {installation_id} for user {user.id}")
            else:
                logger.warning(f"No installations found for user {user.id}")

            await db.commit()
            await db.refresh(github_connection)
            
            return {
                "success": True,
                "user_info": user_info,
                "installations": installations,
                "primary_installation_id": installations[0]["id"] if installations else None,
                "message": "GitHub App connected successfully"
            }
            
        except Exception as e:
            logger.error(f"Error connecting GitHub App for user {user.id}: {str(e)}")
            await db.rollback()
            raise

    async def get_user_repositories(
        self, db: AsyncSession, user: CurrentUser, use_oauth_token: bool = False
    ) -> List[GitHubRepository]:
        """
        Get repositories accessible to the user.

        Args:
            db: Database session
            user: User object
            use_oauth_token: If True, use OAuth token for user's repos only.
                            If False, use installation token for app-accessible repos.

        Returns:
            List of accessible repositories
        """
        try:
            # Get GitHub connection
            result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.supabase_user_id == user.supabase_user_id,
                    GitHubConnection.is_active == True
                )
            )
            github_connection = result.scalars().first()

            if not github_connection or not github_connection.github_access_token:
                return []

            # Try OAuth token first if requested, fall back to installation token if it fails
            if use_oauth_token:
                # Use OAuth access token to get user's repositories only
                access_token = self._decrypt_token(github_connection.github_access_token)

                headers = {
                    "Authorization": f"token {access_token}",
                    "Accept": "application/vnd.github.v3+json"
                }

                # Get user's repositories (personal repos only)
                response = await self.http_client.get(
                    f"{self.api_base_url}/user/repos",
                    headers=headers,
                    params={"sort": "updated", "per_page": 100}
                )

                if response.status_code == 401:
                    logger.warning(f"OAuth token expired or invalid (HTTP 401). Falling back to installation token for user {user.id}")
                    # Fall back to installation token approach
                    use_oauth_token = False
                elif response.status_code != 200:
                    logger.error(f"Failed to get user repositories: HTTP {response.status_code}")
                    return []
                else:
                    # OAuth token worked, parse the response
                    data = response.json()
                    repositories = []

                    for repo_data in data:
                        repository = GitHubRepository(
                            id=repo_data["id"],
                            name=repo_data["name"],
                            full_name=repo_data["full_name"],
                            description=repo_data.get("description"),
                            private=repo_data["private"],
                            html_url=repo_data["html_url"],
                            clone_url=repo_data["clone_url"],
                            ssh_url=repo_data.get("ssh_url", ""),
                            owner=repo_data.get("owner", {}),
                            created_at=repo_data.get("created_at"),
                            updated_at=repo_data.get("updated_at")
                        )
                        repositories.append(repository)

                    user_id = getattr(user, 'id', 'unknown') if user else 'unknown'
                    logger.info(f"Retrieved {len(repositories)} user repositories for user {user_id} using OAuth token")
                    return repositories

            # Use installation token (either as fallback or primary method)
            # Original implementation using installation token for broader access
            # If we have a connection but no installation ID, try to refetch it
            if not github_connection.github_installation_id:
                try:
                    user_id = getattr(user, 'id', 'unknown') if user else 'unknown'
                    logger.info(f"Installation ID missing for user {user_id}, attempting to refetch")
                    access_token = self._decrypt_token(github_connection.github_access_token)

                    # Get user's installations for this app
                    installations = await self._get_user_installations(access_token)

                    if installations:
                        # Update the connection with the installation ID
                        installation_id = installations[0]["id"]
                        github_connection.github_installation_id = installation_id
                        await db.commit()
                        await db.refresh(github_connection)
                        logger.info(f"Refetched and updated installation ID {installation_id} for user {user_id}")
                    else:
                        logger.warning(f"No installations found for user {user_id} during refetch")
                        return []
                except Exception as e:
                    user_id = getattr(user, 'id', 'unknown') if user else 'unknown'
                    logger.error(f"Failed to refetch installation ID for user {user_id}: {str(e)}")
                    return []

            # Get installation access token
            installation_token = await self.get_installation_access_token(
                github_connection.github_installation_id, db, user
            )

            # Get repositories accessible through installation
            headers = {
                "Authorization": f"token {installation_token}",
                "Accept": "application/vnd.github.v3+json"
            }

            response = await self.http_client.get(
                f"{self.api_base_url}/installation/repositories",
                headers=headers
            )

            if response.status_code != 200:
                logger.error(f"Failed to get repositories: HTTP {response.status_code}")
                return []

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
                    ssh_url=repo_data.get("ssh_url", ""),
                    owner=repo_data.get("owner", {}),
                    created_at=repo_data.get("created_at"),
                    updated_at=repo_data.get("updated_at")
                )
                repositories.append(repository)

            user_id = getattr(user, 'id', 'unknown') if user else 'unknown'
            logger.info(f"Retrieved {len(repositories)} repositories for user {user_id} using installation token")
            return repositories

        except Exception as e:
            logger.error(f"Error getting repositories for user {user.id}: {str(e)}")
            return []

    async def get_installation_access_token(self, installation_id: int, db: AsyncSession = None, user: CurrentUser = None) -> str:
        """Get installation access token for repository operations."""
        try:
            # Generate JWT token for authentication
            jwt_token = self.generate_jwt_token()

            # Request installation access token
            url = f"{self.api_base_url}/app/installations/{installation_id}/access_tokens"
            headers = {
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github.v3+json"
            }

            response = await self.http_client.post(url, headers=headers)

            if response.status_code == 201:
                data = response.json()
                return data.get("token")
            elif response.status_code == 404:
                # Installation not found - try to refresh installation ID if we have db and user context
                logger.warning(f"Installation {installation_id} not found (HTTP 404). Attempting to refresh installation ID.")
                if db and user:
                    try:
                        # Try to refetch installation ID using OAuth token
                        result = await db.execute(
                            select(GitHubConnection).filter(
                                GitHubConnection.supabase_user_id == user.supabase_user_id,
                                GitHubConnection.is_active == True
                            )
                        )
                        github_connection = result.scalars().first()

                        if github_connection and github_connection.github_access_token:
                            access_token = self._decrypt_token(github_connection.github_access_token)
                            installations = await self._get_user_installations(access_token)

                            if installations:
                                # Update the connection with the new installation ID
                                new_installation_id = installations[0]["id"]
                                github_connection.github_installation_id = new_installation_id
                                await db.commit()
                                await db.refresh(github_connection)
                                logger.info(f"Refreshed installation ID from {installation_id} to {new_installation_id} for user {user.id}")

                                # Retry with the new installation ID
                                return await self.get_installation_access_token(new_installation_id, db, user)
                            else:
                                logger.warning(f"No installations found during refresh for user {user.id}")
                        else:
                            logger.warning(f"No valid GitHub connection found for user {user.id}")
                    except Exception as refresh_error:
                        logger.error(f"Failed to refresh installation ID: {str(refresh_error)}")

                raise ValueError(f"Installation {installation_id} not found and could not be refreshed")
            else:
                raise ValueError(f"Failed to get installation token: HTTP {response.status_code}")

        except Exception as e:
            logger.error(f"Error getting installation access token: {str(e)}")
            raise

    async def create_repository(
        self,
        db: AsyncSession,
        user: CurrentUser,
        repo_name: str,
        description: str = "",
        private: bool = False,
        use_oauth_token: bool = True
    ) -> Dict[str, Any]:
        """
        Create a new repository.

        Args:
            db: Database session
            user: User object
            repo_name: Repository name
            description: Repository description
            private: Whether repository should be private
            use_oauth_token: If True, use OAuth token (for user's personal repos).
                            If False, use installation token (for org repos where app is installed).

        Returns:
            Repository creation result
        """
        try:
            # Get GitHub connection
            result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.supabase_user_id == user.supabase_user_id,
                    GitHubConnection.is_active == True
                )
            )
            github_connection = result.scalars().first()

            if not github_connection:
                raise ValueError("GitHub account not connected. Please connect your GitHub account first.")

            if not github_connection.github_access_token:
                raise ValueError("GitHub connection is incomplete. Please reconnect your GitHub account.")

            if use_oauth_token:
                # Use OAuth token for personal repository creation
                access_token = self._decrypt_token(github_connection.github_access_token)

                headers = {
                    "Authorization": f"token {access_token}",
                    "Accept": "application/vnd.github.v3+json"
                }

                repo_data = {
                    "name": repo_name,
                    "description": description,
                    "private": private
                }

                response = await self.http_client.post(
                    f"{self.api_base_url}/user/repos",
                    headers=headers,
                    json=repo_data
                )

                if response.status_code != 201:
                    try:
                        error_data = response.json()
                        error_message = error_data.get('message', 'Unknown error')
                        # Add more specific error details if available
                        if 'errors' in error_data:
                            error_details = '; '.join([err.get('message', str(err)) for err in error_data['errors']])
                            error_message += f" ({error_details})"
                        raise ValueError(f"Failed to create repository: {error_message}")
                    except Exception as json_error:
                        # If we can't parse the JSON, show the raw response
                        raise ValueError(f"Failed to create repository: HTTP {response.status_code} - {response.text[:200]}")

                repo_data = response.json()
                logger.info(f"Created personal repository {repo_data['full_name']} for user {user.id}")

            else:
                # Use installation token for organization repository creation
                if not github_connection.github_installation_id:
                    raise ValueError("GitHub App installation required for organization repositories")

                installation_token = await self.get_installation_access_token(
                    github_connection.github_installation_id, db, user
                )

                headers = {
                    "Authorization": f"token {installation_token}",
                    "Accept": "application/vnd.github.v3+json"
                }

                # Get installation info to determine org
                install_response = await self.http_client.get(
                    f"{self.api_base_url}/app/installations/{github_connection.github_installation_id}",
                    headers={"Authorization": f"Bearer {self.generate_jwt_token()}", "Accept": "application/vnd.github.v3+json"}
                )

                if install_response.status_code != 200:
                    raise ValueError("Failed to get installation info")

                install_data = install_response.json()
                account_type = install_data.get("account", {}).get("type", "User")

                if account_type == "Organization":
                    org_name = install_data["account"]["login"]
                    repo_data = {
                        "name": repo_name,
                        "description": description,
                        "private": private
                    }

                    response = await self.http_client.post(
                        f"{self.api_base_url}/orgs/{org_name}/repos",
                        headers=headers,
                        json=repo_data
                    )

                    if response.status_code != 201:
                        try:
                            error_data = response.json()
                            error_message = error_data.get('message', 'Unknown error')
                            if 'errors' in error_data:
                                error_details = '; '.join([err.get('message', str(err)) for err in error_data['errors']])
                                error_message += f" ({error_details})"
                            raise ValueError(f"Failed to create org repository: {error_message}")
                        except Exception as json_error:
                            raise ValueError(f"Failed to create org repository: HTTP {response.status_code} - {response.text[:200]}")

                    repo_data = response.json()
                    logger.info(f"Created organization repository {repo_data['full_name']} for user {user.id}")

                else:
                    # Fallback to personal repo creation
                    repo_data = {
                        "name": repo_name,
                        "description": description,
                        "private": private
                    }

                    response = await self.http_client.post(
                        f"{self.api_base_url}/user/repos",
                        headers=headers,
                        json=repo_data
                    )

                    if response.status_code != 201:
                        try:
                            error_data = response.json()
                            error_message = error_data.get('message', 'Unknown error')
                            if 'errors' in error_data:
                                error_details = '; '.join([err.get('message', str(err)) for err in error_data['errors']])
                                error_message += f" ({error_details})"
                            raise ValueError(f"Failed to create repository: {error_message}")
                        except Exception as json_error:
                            raise ValueError(f"Failed to create repository: HTTP {response.status_code} - {response.text[:200]}")

                    repo_data = response.json()
                    logger.info(f"Created repository {repo_data['full_name']} for user {user.id}")

            return {
                "success": True,
                "repository": {
                    "id": repo_data["id"],
                    "name": repo_data["name"],
                    "full_name": repo_data["full_name"],
                    "html_url": repo_data["html_url"],
                    "private": repo_data["private"],
                    "created_at": repo_data["created_at"]
                },
                "token_type": "OAuth token" if use_oauth_token else "installation token"
            }

        except Exception as e:
            logger.error(f"Error creating repository {repo_name}: {str(e)}")
            raise

    async def sync_files_to_repository(
        self,
        db: AsyncSession,
        user: CurrentUser,
        repository_full_name: str,
        files_content: Dict[str, str],
        commit_message: str,
        branch: str = "main",
        use_oauth_token: bool = False
    ) -> Dict[str, Any]:
        """
        Sync files to a repository.

        Args:
            db: Database session
            user: User object
            repository_full_name: Target repository (owner/repo)
            files_content: Dictionary of file paths to content
            commit_message: Commit message
            branch: Target branch
            use_oauth_token: If True, use OAuth token. If False (default), use installation token.

        Returns:
            Sync result dictionary
        """
        try:
            # Get GitHub connection
            result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.supabase_user_id == user.supabase_user_id,
                    GitHubConnection.is_active == True
                )
            )
            github_connection = result.scalars().first()

            if not github_connection:
                raise ValueError("GitHub account not connected. Please connect your GitHub account first.")

            if not github_connection.github_access_token:
                raise ValueError("GitHub connection is incomplete. Please reconnect your GitHub account.")

            if use_oauth_token:
                # Use OAuth access token
                access_token = self._decrypt_token(github_connection.github_access_token)
                token_type = "OAuth token"
            else:
                # Use installation access token (default for broader access)
                if not github_connection.github_installation_id:
                    raise ValueError("GitHub App installation required for repository operations")

                access_token = await self.get_installation_access_token(
                    github_connection.github_installation_id, db, user
                )
                token_type = "installation token"

            # Sync files using the selected token
            owner, repo = repository_full_name.split("/", 1)
            commit_sha = await self._push_files_to_repo(
                access_token, owner, repo, files_content, commit_message, branch
            )

            return {
                "success": True,
                "commit_sha": commit_sha,
                "files_synced": len(files_content),
                "repository_url": f"https://github.com/{repository_full_name}",
                "commit_url": f"https://github.com/{repository_full_name}/commit/{commit_sha}",
                "token_type": token_type
            }

        except Exception as e:
            logger.error(f"Error syncing files to {repository_full_name}: {str(e)}")
            raise

    # async def _push_files_to_repo(
    #     self,
    #     access_token: str,
    #     owner: str,
    #     repo: str,
    #     files: Dict[str, str],
    #     commit_message: str,
    #     branch: str
    # ) -> str:
    #     """Push files to repository and return commit SHA."""
    #     headers = {
    #         "Authorization": f"token {access_token}",
    #         "Accept": "application/vnd.github.v3+json"
    #     }
        
    #     # Get current branch reference
    #     ref_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/refs/heads/{branch}"
    #     ref_response = await self.http_client.get(ref_url, headers=headers)

    #     if ref_response.status_code in [404, 409]:
    #         # Branch doesn't exist or repository conflict (empty repo), try to find the default branch or create it
    #         default_branch = await self._get_default_branch(headers, owner, repo)
    #         if default_branch and default_branch != branch:
    #             # Use the default branch instead
    #             logger.info(f"Branch '{branch}' not found (HTTP {ref_response.status_code}), using default branch '{default_branch}'")
    #             branch = default_branch
    #             ref_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/refs/heads/{branch}"
    #             ref_response = await self.http_client.get(ref_url, headers=headers)

    #         if ref_response.status_code in [404, 409]:
    #             # Still not found, try to create the branch from an initial commit
    #             logger.info(f"Creating initial branch '{branch}' for repository {owner}/{repo} (HTTP {ref_response.status_code})")
    #             base_sha = await self._create_initial_commit(headers, owner, repo, branch)
    #         else:
    #             ref_data = ref_response.json()
    #             base_sha = ref_data["object"]["sha"]
    #     elif ref_response.status_code != 200:
    #         raise ValueError(f"Failed to get branch reference: HTTP {ref_response.status_code}")
    #     else:
    #         ref_data = ref_response.json()
    #         base_sha = ref_data["object"]["sha"]
        
    #     # Create blobs for each file
    #     tree_items = []
    #     for file_path, content in files.items():
    #         # Create blob
    #         blob_data = {
    #             "content": content,
    #             "encoding": "utf-8"
    #         }
            
    #         blob_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/blobs"
    #         blob_response = await self.http_client.post(blob_url, headers=headers, json=blob_data)
            
    #         if blob_response.status_code != 201:
    #             raise ValueError(f"Failed to create blob for {file_path}: HTTP {blob_response.status_code}")
            
    #         blob_sha = blob_response.json()["sha"]
            
    #         # Add to tree
    #         tree_items.append({
    #             "path": file_path,
    #             "mode": "100644",
    #             "type": "blob",
    #             "sha": blob_sha
    #         })
        
    #     # Create new tree
    #     new_tree_data = {
    #         "base_tree": base_sha,
    #         "tree": tree_items
    #     }
        
    #     new_tree_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/trees"
    #     new_tree_response = await self.http_client.post(new_tree_url, headers=headers, json=new_tree_data)
        
    #     if new_tree_response.status_code != 201:
    #         raise ValueError(f"Failed to create tree: HTTP {new_tree_response.status_code}")
        
    #     new_tree_sha = new_tree_response.json()["sha"]
        
    #     # Create commit
    #     commit_data = {
    #         "message": commit_message,
    #         "tree": new_tree_sha,
    #         "parents": [base_sha]
    #     }
        
    #     commit_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/commits"
    #     commit_response = await self.http_client.post(commit_url, headers=headers, json=commit_data)
        
    #     if commit_response.status_code != 201:
    #         raise ValueError(f"Failed to create commit: HTTP {commit_response.status_code}")
        
    #     commit_sha = commit_response.json()["sha"]
        
    #     # Update branch reference
    #     update_ref_data = {
    #         "sha": commit_sha
    #     }
        
    #     update_ref_response = await self.http_client.patch(ref_url, headers=headers, json=update_ref_data)
        
    #     if update_ref_response.status_code != 200:
    #         raise ValueError(f"Failed to update branch: HTTP {update_ref_response.status_code}")
        
    #     return commit_sha

    async def _push_files_to_repo(
        self,
        access_token: str,
        owner: str,
        repo: str,
        files: Dict[str, str],
        commit_message: str,
        branch: str
    ) -> str:
        """Push files to repository and return commit SHA."""
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json"
        }

        # First, check if repository is empty
        is_empty_repo = await self._is_repository_empty(headers, owner, repo)

        if is_empty_repo:
            logger.info(f"Repository {owner}/{repo} is empty, using Contents API for initial commit")
            return await self._push_files_to_empty_repo(headers, owner, repo, files, commit_message, branch)

        # Repository has commits, use normal Git Data API
        return await self._push_files_to_existing_repo(headers, owner, repo, files, commit_message, branch)

    async def _is_repository_empty(self, headers: Dict[str, str], owner: str, repo: str) -> bool:
        """Check if repository is empty (has no commits)."""
        try:
            # Try to get commits
            commits_url = f"{self.api_base_url}/repos/{owner}/{repo}/commits"
            response = await self.http_client.get(commits_url, headers=headers)

            if response.status_code == 409:
                # 409 means empty repository
                return True
            elif response.status_code == 200:
                commits = response.json()
                return len(commits) == 0

            return False
        except Exception:
            return False

    async def _push_files_to_empty_repo(
        self,
        headers: Dict[str, str],
        owner: str,
        repo: str,
        files: Dict[str, str],
        commit_message: str,
        branch: str
    ) -> str:
        """Push files to an empty repository using Contents API."""
        # For empty repos, we need to create files one by one using Contents API
        # GitHub doesn't allow blob creation in empty repos

        commit_sha = None

        for file_path, content in files.items():
            try:
                # Create file using Contents API
                file_url = f"{self.api_base_url}/repos/{owner}/{repo}/contents/{file_path}"

                file_data = {
                    "message": commit_message if not commit_sha else f"Add {file_path}",
                    "content": base64.b64encode(content.encode()).decode(),
                    "branch": branch
                }

                response = await self.http_client.put(file_url, headers=headers, json=file_data)

                if response.status_code == 201:
                    result = response.json()
                    commit_sha = result.get("commit", {}).get("sha")
                    logger.info(f"Created file {file_path} in empty repo")
                else:
                    error_detail = response.text[:200]
                    logger.error(f"Failed to create {file_path}: HTTP {response.status_code} - {error_detail}")
                    raise ValueError(f"Failed to create file {file_path}: HTTP {response.status_code}")

            except Exception as e:
                logger.error(f"Error creating file {file_path}: {str(e)}")
                raise

        if not commit_sha:
            raise ValueError("No files were created successfully")

        logger.info(f"Successfully created {len(files)} files in empty repository")
        return commit_sha

    async def _push_files_to_existing_repo(
        self,
        headers: Dict[str, str],
        owner: str,
        repo: str,
        files: Dict[str, str],
        commit_message: str,
        branch: str
    ) -> str:
        """Push files to an existing repository using Git Data API."""
        # Get current branch reference
        ref_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/refs/heads/{branch}"
        ref_response = await self.http_client.get(ref_url, headers=headers)

        base_sha = None
        is_new_branch = False

        if ref_response.status_code == 404:
            # Branch doesn't exist, try to get default branch as base
            logger.info(f"Branch '{branch}' not found, checking for default branch")

            default_branch = await self._get_default_branch(headers, owner, repo)

            if default_branch and default_branch != branch:
                # Default branch exists, try to use it as base
                logger.info(f"Using default branch '{default_branch}' as base")
                default_ref_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/refs/heads/{default_branch}"
                default_ref_response = await self.http_client.get(default_ref_url, headers=headers)

                if default_ref_response.status_code == 200:
                    base_sha = default_ref_response.json()["object"]["sha"]
                    is_new_branch = True
                else:
                    raise ValueError(f"Could not find any branch to use as base")
            else:
                raise ValueError(f"Branch '{branch}' not found and no default branch available")

        elif ref_response.status_code == 200:
            # Branch exists, get its SHA
            ref_data = ref_response.json()
            base_sha = ref_data["object"]["sha"]
            logger.info(f"Using existing branch '{branch}' with SHA {base_sha[:7]}")

        else:
            raise ValueError(f"Failed to get branch reference: HTTP {ref_response.status_code} - {ref_response.text}")

        # Create blobs for each file
        tree_items = []
        for file_path, content in files.items():
            blob_data = {
                "content": content,
                "encoding": "utf-8"
            }

            blob_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/blobs"
            blob_response = await self.http_client.post(blob_url, headers=headers, json=blob_data)

            if blob_response.status_code != 201:
                error_detail = blob_response.text[:200]
                raise ValueError(f"Failed to create blob for {file_path}: HTTP {blob_response.status_code} - {error_detail}")

            blob_sha = blob_response.json()["sha"]

            tree_items.append({
                "path": file_path,
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha
            })

        # Create new tree
        new_tree_data = {
            "base_tree": base_sha,
            "tree": tree_items
        }

        new_tree_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/trees"
        new_tree_response = await self.http_client.post(new_tree_url, headers=headers, json=new_tree_data)

        if new_tree_response.status_code != 201:
            error_detail = new_tree_response.text[:200]
            raise ValueError(f"Failed to create tree: HTTP {new_tree_response.status_code} - {error_detail}")

        new_tree_sha = new_tree_response.json()["sha"]

        # Create commit
        commit_data = {
            "message": commit_message,
            "tree": new_tree_sha,
            "parents": [base_sha]
        }

        commit_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/commits"
        commit_response = await self.http_client.post(commit_url, headers=headers, json=commit_data)

        if commit_response.status_code != 201:
            error_detail = commit_response.text[:200]
            raise ValueError(f"Failed to create commit: HTTP {commit_response.status_code} - {error_detail}")

        commit_sha = commit_response.json()["sha"]
        logger.info(f"Created commit {commit_sha[:7]} with {len(files)} files")

        # Update or create branch reference
        if is_new_branch:
            # Create new branch reference
            ref_data = {
                "ref": f"refs/heads/{branch}",
                "sha": commit_sha
            }

            create_ref_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/refs"
            create_ref_response = await self.http_client.post(create_ref_url, headers=headers, json=ref_data)

            if create_ref_response.status_code != 201:
                error_detail = create_ref_response.text[:200]
                raise ValueError(f"Failed to create branch '{branch}': HTTP {create_ref_response.status_code} - {error_detail}")

            logger.info(f"Created new branch '{branch}'")
        else:
            # Update existing branch reference
            update_ref_data = {"sha": commit_sha}
            update_ref_response = await self.http_client.patch(ref_url, headers=headers, json=update_ref_data)

            if update_ref_response.status_code != 200:
                error_detail = update_ref_response.text[:200]
                raise ValueError(f"Failed to update branch '{branch}': HTTP {update_ref_response.status_code} - {error_detail}")

            logger.info(f"Updated branch '{branch}'")

        return commit_sha
    async def _get_default_branch(self, headers: Dict[str, str], owner: str, repo: str) -> Optional[str]:
        """Get the default branch of a repository."""
        try:
            repo_url = f"{self.api_base_url}/repos/{owner}/{repo}"
            response = await self.http_client.get(repo_url, headers=headers)

            if response.status_code == 200:
                repo_data = response.json()
                return repo_data.get("default_branch", "main")

            return None
        except Exception:
            return None

    async def _create_initial_commit(self, headers: Dict[str, str], owner: str, repo: str, branch: str) -> str:
        """Create an initial commit and branch for an empty repository."""
        try:
            # First, check if repository has any commits
            commits_url = f"{self.api_base_url}/repos/{owner}/{repo}/commits"
            commits_response = await self.http_client.get(commits_url, headers=headers)

            if commits_response.status_code == 200:
                # Repository has commits, get the latest commit SHA
                commits_data = commits_response.json()
                if commits_data:
                    latest_commit_sha = commits_data[0]["sha"]
                    logger.info(f"Repository has commits, using latest commit {latest_commit_sha} for branch '{branch}'")

                    # Create branch reference from existing commit
                    ref_data = {
                        "ref": f"refs/heads/{branch}",
                        "sha": latest_commit_sha
                    }

                    ref_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/refs"
                    ref_response = await self.http_client.post(ref_url, headers=headers, json=ref_data)

                    if ref_response.status_code == 201:
                        logger.info(f"Created branch '{branch}' from existing commit {latest_commit_sha}")
                        return latest_commit_sha
                    else:
                        logger.warning(f"Failed to create branch from existing commit: HTTP {ref_response.status_code}")

            # Repository is truly empty or we couldn't get commits, try to create initial commit
            logger.info(f"Repository appears empty, creating initial commit for branch '{branch}'")

            # Create an empty tree
            tree_data = {"tree": []}
            tree_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/trees"
            tree_response = await self.http_client.post(tree_url, headers=headers, json=tree_data)

            if tree_response.status_code != 201:
                # If tree creation fails, try to get the default branch and use its SHA
                default_branch = await self._get_default_branch(headers, owner, repo)
                if default_branch:
                    logger.info(f"Tree creation failed, trying to use default branch '{default_branch}'")
                    default_ref_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/refs/heads/{default_branch}"
                    default_ref_response = await self.http_client.get(default_ref_url, headers=headers)

                    if default_ref_response.status_code == 200:
                        default_ref_data = default_ref_response.json()
                        default_sha = default_ref_data["object"]["sha"]

                        # Create branch reference from default branch
                        ref_data = {
                            "ref": f"refs/heads/{branch}",
                            "sha": default_sha
                        }

                        ref_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/refs"
                        ref_response = await self.http_client.post(ref_url, headers=headers, json=ref_data)

                        if ref_response.status_code == 201:
                            logger.info(f"Created branch '{branch}' from default branch '{default_branch}'")
                            return default_sha

                raise ValueError(f"Failed to create tree: HTTP {tree_response.status_code}")

            tree_sha = tree_response.json()["sha"]

            # Create initial commit
            commit_data = {
                "message": "Initial commit",
                "tree": tree_sha
            }

            commit_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/commits"
            commit_response = await self.http_client.post(commit_url, headers=headers, json=commit_data)

            if commit_response.status_code != 201:
                raise ValueError(f"Failed to create commit: HTTP {commit_response.status_code}")

            commit_sha = commit_response.json()["sha"]

            # Create branch reference
            ref_data = {
                "ref": f"refs/heads/{branch}",
                "sha": commit_sha
            }

            ref_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/refs"
            ref_response = await self.http_client.post(ref_url, headers=headers, json=ref_data)

            if ref_response.status_code != 201:
                raise ValueError(f"Failed to create branch: HTTP {ref_response.status_code}")

            logger.info(f"Created initial branch '{branch}' with commit {commit_sha}")
            return commit_sha

        except Exception as e:
            logger.error(f"Failed to create initial commit: {str(e)}")
            raise ValueError(f"Repository branch creation failed: {str(e)}")

    def _encrypt_token(self, token: str) -> str:
        """Encrypt token for storage (simplified - use proper encryption in production)."""
        # For demo purposes, just base64 encode
        # In production, use proper encryption like Fernet
        return base64.b64encode(token.encode()).decode()

    def _decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt token from storage."""
        try:
            return base64.b64decode(encrypted_token.encode()).decode()
        except Exception:
            return ""

    async def get_connection_status(self, db: AsyncSession, user: CurrentUser) -> Dict[str, Any]:
        """Get GitHub connection status for user."""
        try:
            result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.supabase_user_id == user.supabase_user_id,
                    GitHubConnection.is_active == True
                )
            )
            github_connection = result.scalars().first()

            if not github_connection:
                return {
                    "connected": False,
                    "username": None,
                    "installation_id": None,
                    "repositories_count": 0
                }

            # Get repository count
            repositories = await self.get_user_repositories(db, user)
            repositories_count = len(repositories) if repositories else 0
    
            return {
                "connected": True,
                "username": github_connection.github_username,
                "installation_id": github_connection.github_installation_id,
                "repositories_count": repositories_count,
                "connected_at": github_connection.created_at  # Use created_at until migration runs
            }
            
        except Exception as e:
            logger.error(f"Error getting connection status: {str(e)}")
            return {
                "connected": False,
                "error": str(e)
            }

    async def get_repository_branches(
        self,
        db: AsyncSession,
        user: CurrentUser,
        repository_full_name: str,
        use_oauth_token: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get branches for a repository.

        Args:
            db: Database session
            user: User object
            repository_full_name: Repository in format owner/repo
            use_oauth_token: If True, use OAuth token. If False (default), use installation token.

        Returns:
            List of branch information
        """
        try:
            # Get GitHub connection
            result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.supabase_user_id == user.supabase_user_id,
                    GitHubConnection.is_active == True
                )
            )
            github_connection = result.scalars().first()

            if not github_connection:
                raise ValueError("GitHub account not connected. Please connect your GitHub account first.")

            if not github_connection.github_access_token:
                raise ValueError("GitHub connection is incomplete. Please reconnect your GitHub account.")

            if use_oauth_token:
                # Use OAuth access token
                access_token = self._decrypt_token(github_connection.github_access_token)
                token_type = "OAuth token"
            else:
                # Use installation access token (default for broader access)
                if not github_connection.github_installation_id:
                    raise ValueError("GitHub App installation required for repository operations")

                access_token = await self.get_installation_access_token(
                    github_connection.github_installation_id, db, user
                )
                token_type = "installation token"

            # Get branches from GitHub API
            headers = {
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json"
            }

            owner, repo = repository_full_name.split("/", 1)
            branches_url = f"{self.api_base_url}/repos/{owner}/{repo}/branches"

            response = await self.http_client.get(branches_url, headers=headers)

            if response.status_code != 200:
                error_detail = response.text[:200]
                raise ValueError(f"Failed to get branches: HTTP {response.status_code} - {error_detail}")

            branches_data = response.json()
            branches = []

            for branch_data in branches_data:
                branch_info = {
                    "name": branch_data["name"],
                    "sha": branch_data["commit"]["sha"],
                    "protected": branch_data.get("protected", False),
                    "default": False  # Will be set below
                }
                branches.append(branch_info)

            # Get default branch
            repo_info_url = f"{self.api_base_url}/repos/{owner}/{repo}"
            repo_response = await self.http_client.get(repo_info_url, headers=headers)

            if repo_response.status_code == 200:
                repo_data = repo_response.json()
                default_branch = repo_data.get("default_branch", "main")

                # Mark default branch
                for branch in branches:
                    if branch["name"] == default_branch:
                        branch["default"] = True
                        break

            logger.info(f"Retrieved {len(branches)} branches for {repository_full_name} using {token_type}")
            return branches

        except Exception as e:
            logger.error(f"Error getting branches for {repository_full_name}: {str(e)}")
            raise

    async def create_branch(
        self,
        db: AsyncSession,
        user: CurrentUser,
        repository_full_name: str,
        new_branch_name: str,
        source_branch: str = "main",
        use_oauth_token: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new branch in a repository.

        Args:
            db: Database session
            user: User object
            repository_full_name: Repository in format owner/repo
            new_branch_name: Name of the new branch to create
            source_branch: Source branch to create from (default: "main")
            use_oauth_token: If True, use OAuth token. If False (default), use installation token.

        Returns:
            Branch creation result
        """
        try:
            # Get GitHub connection
            result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.supabase_user_id == user.supabase_user_id,
                    GitHubConnection.is_active == True
                )
            )
            github_connection = result.scalars().first()

            if not github_connection:
                raise ValueError("GitHub account not connected. Please connect your GitHub account first.")

            if not github_connection.github_access_token:
                raise ValueError("GitHub connection is incomplete. Please reconnect your GitHub account.")

            if use_oauth_token:
                # Use OAuth access token
                access_token = self._decrypt_token(github_connection.github_access_token)
                token_type = "OAuth token"
            else:
                # Use installation access token (default for broader access)
                if not github_connection.github_installation_id:
                    raise ValueError("GitHub App installation required for repository operations")

                access_token = await self.get_installation_access_token(
                    github_connection.github_installation_id, db, user
                )
                token_type = "installation token"

            # Get source branch SHA
            headers = {
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json"
            }

            owner, repo = repository_full_name.split("/", 1)
            source_ref_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/refs/heads/{source_branch}"

            source_ref_response = await self.http_client.get(source_ref_url, headers=headers)

            if source_ref_response.status_code != 200:
                error_detail = source_ref_response.text[:200]
                raise ValueError(f"Source branch '{source_branch}' not found: HTTP {source_ref_response.status_code} - {error_detail}")

            source_ref_data = source_ref_response.json()
            source_sha = source_ref_data["object"]["sha"]

            # Create new branch reference
            new_ref_data = {
                "ref": f"refs/heads/{new_branch_name}",
                "sha": source_sha
            }

            create_ref_url = f"{self.api_base_url}/repos/{owner}/{repo}/git/refs"
            create_ref_response = await self.http_client.post(create_ref_url, headers=headers, json=new_ref_data)

            if create_ref_response.status_code != 201:
                error_detail = create_ref_response.text[:200]
                raise ValueError(f"Failed to create branch '{new_branch_name}': HTTP {create_ref_response.status_code} - {error_detail}")

            new_ref_data = create_ref_response.json()

            logger.info(f"Created branch '{new_branch_name}' from '{source_branch}' in {repository_full_name} using {token_type}")

            return {
                "success": True,
                "branch": {
                    "name": new_branch_name,
                    "sha": new_ref_data["object"]["sha"],
                    "url": new_ref_data["url"]
                },
                "source_branch": source_branch,
                "repository": repository_full_name,
                "token_type": token_type
            }

        except Exception as e:
            logger.error(f"Error creating branch '{new_branch_name}' in {repository_full_name}: {str(e)}")
            raise

    async def disconnect_github(self, db: AsyncSession, user: CurrentUser) -> bool:
        """Disconnect GitHub App for user."""
        try:
            result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.supabase_user_id == user.supabase_user_id,
                    GitHubConnection.is_active == True
                )
            )
            github_connection = result.scalars().first()

            if github_connection:
                github_connection.disconnect_github()
                await db.commit()
                logger.info(f"Disconnected GitHub App for user: {user.id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error disconnecting GitHub for user {user.id}: {str(e)}")
            await db.rollback()
            return False