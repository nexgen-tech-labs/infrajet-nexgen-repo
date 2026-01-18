"""
GitHub App integration service.

This service handles GitHub App authentication, repository operations,
and webhook handling for installation events.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import jwt
import httpx
from logconfig.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.settings import get_settings
from app.models.user import User, GitHubConnection
from app.schemas.github import GitHubRepository, GitHubInstallation, GitHubWebhookEvent
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

logger = get_logger()
settings = get_settings()


class GitHubAppError(Exception):
    """Base exception for GitHub App operations."""
    pass


class GitHubAppAuthError(GitHubAppError):
    """Exception for GitHub App authentication errors."""
    pass


class GitHubAppAPIError(GitHubAppError):
    """Exception for GitHub App API errors."""
    pass


class GitHubAppRateLimitError(GitHubAppError):
    """Exception for GitHub App rate limit errors."""
    pass


class GitHubAppService:
    """
    Service for handling GitHub App authentication and repository operations.
    
    This service provides GitHub App JWT token generation, installation token
    retrieval, repository operations, and webhook handling.
    """

    def __init__(self):
        """Initialize the GitHub App service."""
        self.app_id = settings.GITHUB_APP_ID
        self.client_id = settings.GITHUB_CLIENT_ID
        self.client_secret = settings.GITHUB_CLIENT_SECRET
        self.private_key = settings.GITHUB_PRIVATE_KEY
        self.webhook_secret = settings.GITHUB_WEBHOOK_SECRET
        
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
        
        # Validate configuration on initialization
        self._validate_configuration()

    def _validate_configuration(self) -> None:
        """
        Validate GitHub App configuration.
        
        Raises:
            GitHubAppError: If configuration is invalid
        """
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
            raise GitHubAppError(
                f"GitHub App configuration incomplete. Missing: {', '.join(missing_configs)}"
            )

    def is_configured(self) -> bool:
        """
        Check if GitHub App is properly configured.
        
        Returns:
            bool: True if properly configured, False otherwise
        """
        try:
            self._validate_configuration()
            return True
        except GitHubAppError:
            return False

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the GitHub App service.
        
        Returns:
            Dict with health check results
        """
        health_status = {
            "service": "GitHub App",
            "status": "healthy",
            "checks": {},
            "errors": []
        }
        
        # Check configuration
        try:
            self._validate_configuration()
            health_status["checks"]["configuration"] = "✓ Valid"
        except GitHubAppError as e:
            health_status["checks"]["configuration"] = f"✗ Invalid: {e}"
            health_status["errors"].append(str(e))
            health_status["status"] = "unhealthy"
        
        # Check JWT token generation
        try:
            jwt_token = self.generate_jwt_token()
            health_status["checks"]["jwt_generation"] = "✓ Working"
        except Exception as e:
            health_status["checks"]["jwt_generation"] = f"✗ Failed: {e}"
            health_status["errors"].append(f"JWT generation failed: {e}")
            health_status["status"] = "unhealthy"
        
        # Check GitHub API connectivity (if JWT generation works)
        if "jwt_generation" in health_status["checks"] and "✓" in health_status["checks"]["jwt_generation"]:
            try:
                url = f"{self.api_base_url}/app"
                headers = {
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                
                response = await self.http_client.get(url, headers=headers, timeout=10.0)
                if response.status_code == 200:
                    health_status["checks"]["api_connectivity"] = "✓ Connected"
                else:
                    health_status["checks"]["api_connectivity"] = f"✗ HTTP {response.status_code}"
                    health_status["errors"].append(f"API connectivity failed: HTTP {response.status_code}")
                    if health_status["status"] == "healthy":
                        health_status["status"] = "degraded"
                        
            except Exception as e:
                health_status["checks"]["api_connectivity"] = f"✗ Failed: {e}"
                health_status["errors"].append(f"API connectivity failed: {e}")
                if health_status["status"] == "healthy":
                    health_status["status"] = "degraded"
        
        return health_status

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.http_client.aclose()

    def generate_jwt_token(self) -> str:
        """
        Generate GitHub App JWT token for authentication.
        
        Returns:
            JWT token string
            
        Raises:
            GitHubAppAuthError: If token generation fails
        """
        if not self.app_id or not self.private_key:
            raise GitHubAppAuthError("GitHub App ID and private key are required")
        
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
            
            # Check if it's a placeholder or invalid key
            if private_key == "your-github-app-private-key-here" or not private_key:
                raise GitHubAppAuthError("GitHub App private key not configured. Please set GITHUB_PRIVATE_KEY environment variable.")
            
            if private_key.startswith("-----BEGIN"):
                # Already in PEM format
                pass
            else:
                # Try to decode from base64
                try:
                    private_key = base64.b64decode(private_key).decode('utf-8')
                except Exception as e:
                    logger.warning(f"Failed to decode private key from base64, using as-is: {e}")
                    # If decoding fails, use as-is and let JWT library handle it
            
            # Generate JWT token
            token = jwt.encode(payload, private_key, algorithm="RS256")
            
            logger.debug("Generated GitHub App JWT token")
            return token
            
        except Exception as e:
            logger.error(f"Failed to generate GitHub App JWT token: {str(e)}")
            raise GitHubAppAuthError(f"Failed to generate JWT token: {str(e)}")

    async def get_installation_access_token(self, installation_id: int) -> str:
        """
        Get installation access token for repository operations.
        
        Args:
            installation_id: GitHub App installation ID
            
        Returns:
            Installation access token
            
        Raises:
            GitHubAppAuthError: If token retrieval fails
        """
        try:
            # Generate JWT token for authentication
            jwt_token = self.generate_jwt_token()
            
            # Request installation access token
            url = f"{self.api_base_url}/app/installations/{installation_id}/access_tokens"
            headers = {
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            response = await self._make_api_request_with_retry(
                "POST", url, headers, operation=f"get installation token for {installation_id}"
            )
            
            if response.status_code == 201:
                data = response.json()
                token = data.get("token")
                expires_at = data.get("expires_at")
                
                logger.info(f"Retrieved installation access token for installation {installation_id}, expires at {expires_at}")
                return token
            elif response.status_code == 404:
                raise GitHubAppAuthError(f"Installation {installation_id} not found")
            elif response.status_code == 403:
                raise GitHubAppAuthError(f"Access denied to installation {installation_id}")
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("message", f"HTTP {response.status_code}")
                raise GitHubAppAuthError(f"Failed to get installation token: {error_msg}")
                
        except GitHubAppAuthError:
            raise
        except Exception as e:
            logger.error(f"Error getting installation access token: {str(e)}")
            raise GitHubAppAuthError(f"Failed to get installation token: {str(e)}")

    async def get_user_installations(self, user_access_token: str) -> List[GitHubInstallation]:
        """
        Get GitHub App installations accessible to a user.
        
        Args:
            user_access_token: User's GitHub access token
            
        Returns:
            List of GitHubInstallation objects
            
        Raises:
            GitHubAppAPIError: If API request fails
        """
        try:
            url = f"{self.api_base_url}/user/installations"
            headers = {
                "Authorization": f"token {user_access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            response = await self._make_api_request_with_retry(
                "GET", url, headers, operation="get user installations"
            )
            
            if response.status_code == 200:
                data = response.json()
                installations = []
                
                for install_data in data.get("installations", []):
                    installation = GitHubInstallation(
                        id=install_data["id"],
                        account_login=install_data["account"]["login"],
                        account_type=install_data["account"]["type"],
                        permissions=install_data.get("permissions", {}),
                        events=install_data.get("events", []),
                        created_at=datetime.fromisoformat(install_data["created_at"].replace("Z", "+00:00")),
                        updated_at=datetime.fromisoformat(install_data["updated_at"].replace("Z", "+00:00"))
                    )
                    installations.append(installation)
                
                logger.info(f"Retrieved {len(installations)} installations for user")
                return installations
            else:
                await self._handle_api_error(response, "get user installations")
                
        except GitHubAppAPIError:
            raise
        except Exception as e:
            logger.error(f"Error getting user installations: {str(e)}")
            raise GitHubAppAPIError(f"Failed to get user installations: {str(e)}")

    async def create_repository(
        self, 
        installation_id: int,
        repo_name: str, 
        description: Optional[str] = None,
        private: bool = True,
        owner: Optional[str] = None
    ) -> GitHubRepository:
        """
        Create a new repository using GitHub App.
        
        Args:
            installation_id: GitHub App installation ID
            repo_name: Repository name
            description: Repository description
            private: Whether repository should be private
            owner: Repository owner (organization name, if applicable)
            
        Returns:
            GitHubRepository object
            
        Raises:
            GitHubAppAPIError: If repository creation fails
        """
        try:
            # Get installation access token
            access_token = await self.get_installation_access_token(installation_id)
            
            # Prepare repository data
            repo_data = {
                "name": repo_name,
                "private": private,
                "auto_init": True,  # Initialize with README
                "description": description or f"Infrastructure code repository created by InfraJet"
            }
            
            # Determine API endpoint
            if owner:
                # Create in organization
                url = f"{self.api_base_url}/orgs/{owner}/repos"
            else:
                # Create in user account (installation account)
                url = f"{self.api_base_url}/user/repos"
            
            headers = {
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            response = await self.http_client.post(url, headers=headers, json=repo_data)
            
            if response.status_code == 201:
                data = response.json()
                repository = GitHubRepository(
                    id=data["id"],
                    name=data["name"],
                    full_name=data["full_name"],
                    description=data.get("description"),
                    private=data["private"],
                    html_url=data["html_url"],
                    clone_url=data["clone_url"],
                    created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
                    updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
                )
                
                logger.info(f"Created repository {repository.full_name}")
                return repository
            else:
                await self._handle_api_error(response, "create repository")
                
        except GitHubAppAPIError:
            raise
        except Exception as e:
            logger.error(f"Error creating repository {repo_name}: {str(e)}")
            raise GitHubAppAPIError(f"Failed to create repository: {str(e)}")

    async def push_files(
        self,
        installation_id: int,
        repo_owner: str,
        repo_name: str,
        files: Dict[str, str],
        commit_message: str,
        branch: str = "main"
    ) -> str:
        """
        Push files to repository using GitHub App.
        
        Args:
            installation_id: GitHub App installation ID
            repo_owner: Repository owner
            repo_name: Repository name
            files: Dictionary of file paths to content
            commit_message: Commit message
            branch: Target branch
            
        Returns:
            Commit SHA
            
        Raises:
            GitHubAppAPIError: If push operation fails
        """
        try:
            # Get installation access token
            access_token = await self.get_installation_access_token(installation_id)
            
            headers = {
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            # Get current branch reference
            ref_url = f"{self.api_base_url}/repos/{repo_owner}/{repo_name}/git/refs/heads/{branch}"
            ref_response = await self.http_client.get(ref_url, headers=headers)
            
            if ref_response.status_code != 200:
                await self._handle_api_error(ref_response, "get branch reference")
            
            ref_data = ref_response.json()
            base_sha = ref_data["object"]["sha"]
            
            # Get base tree
            tree_url = f"{self.api_base_url}/repos/{repo_owner}/{repo_name}/git/trees/{base_sha}"
            tree_response = await self.http_client.get(tree_url, headers=headers)
            
            if tree_response.status_code != 200:
                await self._handle_api_error(tree_response, "get base tree")
            
            # Create blobs for each file
            tree_items = []
            for file_path, content in files.items():
                # Create blob
                blob_data = {
                    "content": content,
                    "encoding": "utf-8"
                }
                
                blob_url = f"{self.api_base_url}/repos/{repo_owner}/{repo_name}/git/blobs"
                blob_response = await self.http_client.post(blob_url, headers=headers, json=blob_data)
                
                if blob_response.status_code != 201:
                    await self._handle_api_error(blob_response, f"create blob for {file_path}")
                
                blob_sha = blob_response.json()["sha"]
                
                # Add to tree
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
            
            new_tree_url = f"{self.api_base_url}/repos/{repo_owner}/{repo_name}/git/trees"
            new_tree_response = await self.http_client.post(new_tree_url, headers=headers, json=new_tree_data)
            
            if new_tree_response.status_code != 201:
                await self._handle_api_error(new_tree_response, "create new tree")
            
            new_tree_sha = new_tree_response.json()["sha"]
            
            # Create commit
            commit_data = {
                "message": commit_message,
                "tree": new_tree_sha,
                "parents": [base_sha]
            }
            
            commit_url = f"{self.api_base_url}/repos/{repo_owner}/{repo_name}/git/commits"
            commit_response = await self.http_client.post(commit_url, headers=headers, json=commit_data)
            
            if commit_response.status_code != 201:
                await self._handle_api_error(commit_response, "create commit")
            
            commit_sha = commit_response.json()["sha"]
            
            # Update branch reference
            update_ref_data = {
                "sha": commit_sha
            }
            
            update_ref_response = await self.http_client.patch(ref_url, headers=headers, json=update_ref_data)
            
            if update_ref_response.status_code != 200:
                await self._handle_api_error(update_ref_response, "update branch reference")
            
            logger.info(f"Pushed {len(files)} files to {repo_owner}/{repo_name}, commit: {commit_sha}")
            return commit_sha
            
        except GitHubAppAPIError:
            raise
        except Exception as e:
            logger.error(f"Error pushing files to {repo_owner}/{repo_name}: {str(e)}")
            raise GitHubAppAPIError(f"Failed to push files: {str(e)}")

    async def sync_repository(
        self,
        installation_id: int,
        repo_owner: str,
        repo_name: str,
        files: Dict[str, str],
        commit_message: str,
        branch: str = "main"
    ) -> Dict[str, Any]:
        """
        Sync files to repository with conflict detection.
        
        Args:
            installation_id: GitHub App installation ID
            repo_owner: Repository owner
            repo_name: Repository name
            files: Dictionary of file paths to content
            commit_message: Commit message
            branch: Target branch
            
        Returns:
            Dictionary with sync results
            
        Raises:
            GitHubAppAPIError: If sync operation fails
        """
        try:
            # Get installation access token
            access_token = await self.get_installation_access_token(installation_id)
            
            # Check if repository exists
            repo_url = f"{self.api_base_url}/repos/{repo_owner}/{repo_name}"
            headers = {
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            repo_response = await self.http_client.get(repo_url, headers=headers)
            
            if repo_response.status_code == 404:
                raise GitHubAppAPIError(f"Repository {repo_owner}/{repo_name} not found")
            elif repo_response.status_code != 200:
                await self._handle_api_error(repo_response, "check repository")
            
            # Push files
            commit_sha = await self.push_files(
                installation_id=installation_id,
                repo_owner=repo_owner,
                repo_name=repo_name,
                files=files,
                commit_message=commit_message,
                branch=branch
            )
            
            return {
                "success": True,
                "commit_sha": commit_sha,
                "files_synced": len(files),
                "repository_url": f"https://github.com/{repo_owner}/{repo_name}",
                "commit_url": f"https://github.com/{repo_owner}/{repo_name}/commit/{commit_sha}"
            }
            
        except GitHubAppAPIError:
            raise
        except Exception as e:
            logger.error(f"Error syncing repository {repo_owner}/{repo_name}: {str(e)}")
            raise GitHubAppAPIError(f"Failed to sync repository: {str(e)}")

    async def delete_repository(
        self,
        access_token: str,
        repo_name: str
    ) -> bool:
        """
        Delete a GitHub repository.
        
        Args:
            access_token: GitHub access token
            repo_name: Repository name to delete
            
        Returns:
            bool: True if deletion was successful
            
        Raises:
            GitHubAppAPIError: If deletion fails
        """
        try:
            # Get repository owner from the access token or installation
            # For simplicity, we'll assume the repo_name includes the owner
            if "/" not in repo_name:
                # If no owner specified, we need to get it from the installation
                logger.warning(f"Repository name {repo_name} does not include owner")
                return False
            
            owner, repo = repo_name.split("/", 1)
            
            url = f"{self.api_base_url}/repos/{owner}/{repo}"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            response = await self._make_api_request_with_retry(
                method="DELETE",
                url=url,
                headers=headers
            )
            
            if response.status_code == 204:
                logger.info(f"Successfully deleted repository {repo_name}")
                return True
            else:
                await self._handle_api_error(response, f"delete repository {repo_name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete repository {repo_name}: {e}")
            raise GitHubAppAPIError(f"Failed to delete repository: {str(e)}")

    async def validate_user_repository_access(
        self,
        user_access_token: str,
        installation_id: int,
        repo_owner: str,
        repo_name: str
    ) -> bool:
        """
        Validate user access to repository through GitHub App installation.
        
        Args:
            user_access_token: User's GitHub access token
            installation_id: GitHub App installation ID
            repo_owner: Repository owner
            repo_name: Repository name
            
        Returns:
            True if user has access, False otherwise
        """
        try:
            # Get user installations
            installations = await self.get_user_installations(user_access_token)
            
            # Check if installation_id is in user's installations
            user_installation_ids = [install.id for install in installations]
            if installation_id not in user_installation_ids:
                logger.warning(f"User does not have access to installation {installation_id}")
                return False
            
            # Get installation access token
            access_token = await self.get_installation_access_token(installation_id)
            
            # Check repository access
            repo_url = f"{self.api_base_url}/repos/{repo_owner}/{repo_name}"
            headers = {
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            response = await self.http_client.get(repo_url, headers=headers)
            
            if response.status_code == 200:
                logger.info(f"User has access to repository {repo_owner}/{repo_name} through installation {installation_id}")
                return True
            elif response.status_code == 404:
                logger.warning(f"Repository {repo_owner}/{repo_name} not found or not accessible")
                return False
            else:
                logger.warning(f"Unexpected response when checking repository access: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error validating repository access: {str(e)}")
            return False

    def validate_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Validate GitHub webhook signature.
        
        Args:
            payload: Webhook payload bytes
            signature: GitHub signature header
            
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured, skipping signature validation")
            return True
        
        try:
            # Remove 'sha256=' prefix if present
            if signature.startswith("sha256="):
                signature = signature[7:]
            
            # Calculate expected signature
            expected_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            is_valid = hmac.compare_digest(signature, expected_signature)
            
            if not is_valid:
                logger.warning("Invalid webhook signature")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error validating webhook signature: {str(e)}")
            return False

    async def handle_webhook_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle GitHub App webhook events.
        
        Args:
            event_type: GitHub event type
            payload: Webhook payload
            
        Returns:
            Dictionary with handling results
        """
        try:
            logger.info(f"Handling GitHub webhook event: {event_type}")
            
            if event_type == "installation":
                return await self._handle_installation_event(payload)
            elif event_type == "installation_repositories":
                return await self._handle_installation_repositories_event(payload)
            elif event_type == "push":
                return await self._handle_push_event(payload)
            else:
                logger.info(f"Unhandled webhook event type: {event_type}")
                return {"handled": False, "message": f"Event type {event_type} not handled"}
                
        except Exception as e:
            logger.error(f"Error handling webhook event {event_type}: {str(e)}")
            return {"handled": False, "error": str(e)}

    async def _handle_installation_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle installation webhook events."""
        action = payload.get("action")
        installation = payload.get("installation", {})
        installation_id = installation.get("id")
        account = installation.get("account", {})
        github_user_id = account.get("id")
        github_username = account.get("login")

        logger.info(f"Installation event: {action} for installation {installation_id} (user: {github_username})")

        try:
            # Get database session
            db = await get_db().__aenter__()

            if action == "created":
                # Try to find user by GitHub user ID through GitHub connections table
                github_connection = None
                if github_user_id:
                    result = await db.execute(
                        select(GitHubConnection).filter(
                            GitHubConnection.github_user_id == github_user_id,
                            GitHubConnection.connection_type == "oauth"
                        )
                    )
                    github_connection = result.scalars().first()

                if github_connection:
                    # Get the user associated with this connection
                    user_result = await db.execute(
                        select(User).filter(User.supabase_user_id == github_connection.supabase_user_id)
                    )
                    user = user_result.scalars().first()

                    if user:
                        # Update the GitHub connection with app details
                        github_connection.connect_github_app(
                            installation_id=installation_id,
                            app_id=settings.GITHUB_APP_ID
                        )
                        await db.commit()
                        await db.refresh(github_connection)

                        logger.info(f"Linked installation {installation_id} to user {user.id}")
                        return {"handled": True, "message": f"Installation linked to user {user.id}"}

                # User hasn't connected OAuth yet, create a placeholder connection for app
                if github_user_id:
                    # Check if we already have a placeholder connection
                    result = await db.execute(
                        select(GitHubConnection).filter(
                            GitHubConnection.github_user_id == github_user_id,
                            GitHubConnection.connection_type == "app"
                        )
                    )
                    existing_connection = result.scalars().first()

                    if not existing_connection:
                        # Create a new connection record for the app (will be linked to user later)
                        placeholder_connection = GitHubConnection(
                            supabase_user_id=f"pending-{github_user_id}",  # Temporary ID
                            connection_type="app"
                        )
                        placeholder_connection.connect_github_app(
                            installation_id=installation_id,
                            app_id=settings.GITHUB_APP_ID
                        )
                        db.add(placeholder_connection)
                        await db.commit()

                        logger.info(f"Created placeholder app connection for GitHub user {github_user_id}")
                        return {"handled": True, "message": "App installation recorded, awaiting user OAuth connection"}

                logger.info(f"Installation {installation_id} created but no matching user found yet")
                return {"handled": True, "message": "Installation created, awaiting user connection"}

            elif action == "deleted":
                # Find and unlink installation from user
                result = await db.execute(
                    select(User).filter(User.github_installation_id == installation_id)
                )
                user = result.scalars().first()

                if user:
                    user.disconnect_github_app()
                    await db.commit()
                    logger.info(f"Unlinked installation {installation_id} from user {user.id}")
                    return {"handled": True, "message": f"Installation unlinked from user {user.id}"}
                else:
                    logger.warning(f"Installation {installation_id} deleted but no matching user found")
                    return {"handled": True, "message": "Installation deleted"}

            else:
                return {"handled": False, "message": f"Unhandled installation action: {action}"}

        except Exception as e:
            logger.error(f"Error handling installation event: {str(e)}")
            return {"handled": False, "error": str(e)}
        finally:
            try:
                await db.close()
            except:
                pass

    async def _handle_installation_repositories_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle installation repositories webhook events."""
        action = payload.get("action")
        installation = payload.get("installation", {})
        
        logger.info(f"Installation repositories event: {action} for installation {installation.get('id')}")
        
        return {"handled": True, "message": f"Installation repositories {action}"}

    async def _handle_push_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle push webhook events."""
        repository = payload.get("repository", {})
        ref = payload.get("ref", "")
        
        logger.info(f"Push event to {repository.get('full_name')} on {ref}")
        
        return {"handled": True, "message": "Push event processed"}

    async def _handle_api_error(self, response: httpx.Response, operation: str) -> None:
        """
        Handle GitHub API error responses.
        
        Args:
            response: HTTP response object
            operation: Description of the operation that failed
            
        Raises:
            GitHubAppRateLimitError: If rate limit exceeded
            GitHubAppAPIError: For other API errors
        """
        try:
            error_data = response.json() if response.content else {}
        except json.JSONDecodeError:
            error_data = {}
        
        error_message = error_data.get("message", f"HTTP {response.status_code}")
        
        # Log rate limit information for debugging
        if response.headers.get("X-RateLimit-Limit"):
            logger.debug(f"Rate limit info - Limit: {response.headers.get('X-RateLimit-Limit')}, "
                        f"Remaining: {response.headers.get('X-RateLimit-Remaining')}, "
                        f"Reset: {response.headers.get('X-RateLimit-Reset')}")
        
        if response.status_code == 403:
            # Check if it's a rate limit error
            if ("rate limit" in error_message.lower() or 
                response.headers.get("X-RateLimit-Remaining") == "0"):
                
                reset_time = response.headers.get("X-RateLimit-Reset")
                remaining = response.headers.get("X-RateLimit-Remaining", "0")
                
                if reset_time:
                    reset_datetime = datetime.fromtimestamp(int(reset_time))
                    raise GitHubAppRateLimitError(
                        f"Rate limit exceeded for {operation}. "
                        f"Remaining: {remaining}, Resets at {reset_datetime}"
                    )
                else:
                    raise GitHubAppRateLimitError(f"Rate limit exceeded for {operation}")
            else:
                # Check for specific permission errors
                if "permission" in error_message.lower():
                    raise GitHubAppAPIError(f"Insufficient permissions for {operation}: {error_message}")
                else:
                    raise GitHubAppAPIError(f"Access denied for {operation}: {error_message}")
        elif response.status_code == 404:
            raise GitHubAppAPIError(f"Resource not found for {operation}: {error_message}")
        elif response.status_code == 422:
            # Validation error
            errors = error_data.get("errors", [])
            if errors:
                error_details = "; ".join([err.get("message", str(err)) for err in errors])
                raise GitHubAppAPIError(f"Validation error for {operation}: {error_details}")
            else:
                raise GitHubAppAPIError(f"Validation error for {operation}: {error_message}")
        elif response.status_code >= 500:
            raise GitHubAppAPIError(f"GitHub server error for {operation}: {error_message}")
        else:
            raise GitHubAppAPIError(f"GitHub API error for {operation}: {error_message}")

    async def _make_api_request_with_retry(
        self, 
        method: str, 
        url: str, 
        headers: Dict[str, str], 
        json_data: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        operation: str = "API request"
    ) -> httpx.Response:
        """
        Make API request with retry logic for rate limits and transient errors.
        
        Args:
            method: HTTP method
            url: Request URL
            headers: Request headers
            json_data: JSON payload
            max_retries: Maximum number of retries
            operation: Description of the operation
            
        Returns:
            httpx.Response: API response
            
        Raises:
            GitHubAppRateLimitError: If rate limit exceeded after retries
            GitHubAppAPIError: For other API errors
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                if method.upper() == "GET":
                    response = await self.http_client.get(url, headers=headers)
                elif method.upper() == "POST":
                    response = await self.http_client.post(url, headers=headers, json=json_data)
                elif method.upper() == "PATCH":
                    response = await self.http_client.patch(url, headers=headers, json=json_data)
                else:
                    raise GitHubAppAPIError(f"Unsupported HTTP method: {method}")
                
                # If successful, return response
                if response.status_code < 400:
                    return response
                
                # Handle rate limit with exponential backoff
                if response.status_code == 403 and "rate limit" in response.text.lower():
                    if attempt < max_retries:
                        wait_time = 2 ** attempt  # Exponential backoff
                        logger.warning(f"Rate limit hit for {operation}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries + 1})")
                        await asyncio.sleep(wait_time)
                        continue
                
                # Handle server errors with retry
                if response.status_code >= 500 and attempt < max_retries:
                    wait_time = 2 ** attempt
                    logger.warning(f"Server error for {operation}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries + 1})")
                    await asyncio.sleep(wait_time)
                    continue
                
                # If we get here, handle the error
                await self._handle_api_error(response, operation)
                
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exception = e
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    logger.warning(f"Network error for {operation}, retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise GitHubAppAPIError(f"Network error for {operation} after {max_retries} retries: {e}")
            except GitHubAppRateLimitError:
                # Don't retry rate limit errors that we've already handled
                raise
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    logger.warning(f"Unexpected error for {operation}, retrying in {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise GitHubAppAPIError(f"Unexpected error for {operation}: {e}")
        
        # If we get here, all retries failed
        if last_exception:
            raise GitHubAppAPIError(f"Operation {operation} failed after {max_retries} retries: {last_exception}")
        else:
            raise GitHubAppAPIError(f"Operation {operation} failed after {max_retries} retries")


# Global service instance (lazy initialization)
_github_app_service: Optional[GitHubAppService] = None


async def get_github_app_service() -> GitHubAppService:
    """Get GitHub App service instance with lazy initialization."""
    global _github_app_service
    if _github_app_service is None:
        _github_app_service = GitHubAppService()
    return _github_app_service


def get_github_app_service_sync() -> GitHubAppService:
    """Get GitHub App service instance synchronously with lazy initialization."""
    global _github_app_service
    if _github_app_service is None:
        _github_app_service = GitHubAppService()
    return _github_app_service