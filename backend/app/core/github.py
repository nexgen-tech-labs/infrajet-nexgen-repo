"""
GitHub OAuth2 configuration and utilities.
"""

import secrets
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging
import aiohttp
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class GitHubConfig(BaseModel):
    """GitHub OAuth2 configuration settings."""

    client_id: str = Field(..., description="GitHub OAuth app client ID")
    client_secret: str = Field(..., description="GitHub OAuth app client secret")
    redirect_uri: str = Field(..., description="OAuth2 redirect URI")
    scopes: List[str] = Field(
        default=["repo", "user:email"],
        description="OAuth2 scopes to request",
    )
    api_base_url: str = Field(
        default="https://api.github.com",
        description="GitHub API base URL"
    )
    authorize_url: str = Field(
        default="https://github.com/login/oauth/authorize",
        description="GitHub OAuth authorization URL"
    )
    token_url: str = Field(
        default="https://github.com/login/oauth/access_token",
        description="GitHub OAuth token exchange URL"
    )

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: List[str]) -> List[str]:
        """Ensure required scopes are present."""
        required_scopes = {"repo", "user:email"}
        current_scopes = set(v)

        # Add missing required scopes
        missing_scopes = required_scopes - current_scopes
        if missing_scopes:
            v.extend(list(missing_scopes))

        return v

    def is_configured(self) -> bool:
        """Check if GitHub OAuth is properly configured."""
        return bool(
            self.client_id
            and self.client_secret
            and self.redirect_uri
        )


class GitHubTokenResponse(BaseModel):
    """GitHub OAuth token response model."""

    access_token: str
    token_type: str = "bearer"
    scope: Optional[str] = None


class GitHubUserProfile(BaseModel):
    """GitHub user profile model."""

    id: int = Field(..., description="GitHub user ID")
    login: str = Field(..., description="GitHub username")
    email: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    html_url: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    public_repos: Optional[int] = None
    followers: Optional[int] = None
    following: Optional[int] = None
    created_at: Optional[str] = None


class GitHubRepository(BaseModel):
    """GitHub repository model."""

    id: int
    name: str
    full_name: str
    description: Optional[str] = None
    private: bool
    html_url: str
    clone_url: str
    ssh_url: str
    default_branch: str = "main"
    permissions: Optional[Dict[str, bool]] = None
    owner: Dict[str, Any]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    pushed_at: Optional[str] = None


class GitHubCommitResponse(BaseModel):
    """GitHub commit response model."""

    sha: str
    html_url: str
    commit: Dict[str, Any]
    author: Optional[Dict[str, Any]] = None
    committer: Optional[Dict[str, Any]] = None


class GitHubFileContent(BaseModel):
    """GitHub file content model."""

    name: str
    path: str
    sha: str
    size: int
    url: str
    html_url: str
    git_url: str
    download_url: Optional[str] = None
    type: str  # "file" or "dir"
    content: Optional[str] = None  # Base64 encoded
    encoding: Optional[str] = None


class GitHubError(Exception):
    """Base exception for GitHub API errors."""
    pass


class GitHubAuthError(GitHubError):
    """Raised when GitHub authentication fails."""
    pass


class GitHubAPIError(GitHubError):
    """Raised when GitHub API calls fail."""
    pass


class RepositoryNotFoundError(GitHubError):
    """Raised when a repository is not found."""
    pass


class InsufficientPermissionsError(GitHubError):
    """Raised when user lacks required permissions."""
    pass


class GitHubService:
    """GitHub OAuth2 and API service."""

    def __init__(self, config: GitHubConfig):
        """Initialize the GitHub service with configuration."""
        self.config = config
        self._session = None

    @property
    async def session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session for API calls."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate GitHub authorization URL for OAuth2 flow.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Authorization URL string
        """
        if state is None:
            state = secrets.token_urlsafe(32)

        try:
            params = {
                "client_id": self.config.client_id,
                "redirect_uri": self.config.redirect_uri,
                "scope": " ".join(self.config.scopes),
                "state": state,
                "allow_signup": "true"
            }

            # Build URL with parameters
            param_string = "&".join([f"{k}={v}" for k, v in params.items()])
            auth_url = f"{self.config.authorize_url}?{param_string}"

            logger.info(f"Generated GitHub authorization URL for state: {state}")
            return auth_url

        except Exception as e:
            logger.error(f"Failed to generate GitHub authorization URL: {str(e)}")
            raise GitHubError(f"Failed to generate authorization URL: {str(e)}")

    async def exchange_code_for_token(self, code: str) -> GitHubTokenResponse:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from callback

        Returns:
            GitHubTokenResponse with access token
        """
        try:
            session = await self.session

            data = {
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "code": code,
                "redirect_uri": self.config.redirect_uri,
            }

            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            async with session.post(
                self.config.token_url, data=data, headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"GitHub token exchange failed: {error_text}")
                    raise GitHubAuthError(f"Token exchange failed: {error_text}")

                result = await response.json()

                if "error" in result:
                    error_msg = result.get("error_description", result.get("error"))
                    logger.error(f"GitHub token exchange error: {error_msg}")
                    raise GitHubAuthError(f"Token exchange error: {error_msg}")

                logger.info("Successfully exchanged code for GitHub token")
                return GitHubTokenResponse(
                    access_token=result["access_token"],
                    token_type=result.get("token_type", "bearer"),
                    scope=result.get("scope"),
                )

        except Exception as e:
            if isinstance(e, GitHubError):
                raise
            logger.error(f"Failed to exchange code for GitHub token: {str(e)}")
            raise GitHubError(f"Failed to exchange code for token: {str(e)}")

    async def get_user_profile(self, access_token: str) -> GitHubUserProfile:
        """
        Retrieve user profile from GitHub API.

        Args:
            access_token: Valid GitHub access token

        Returns:
            GitHubUserProfile with user information
        """
        try:
            session = await self.session
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Infrajet-Backend/1.0",
            }

            async with session.get(
                f"{self.config.api_base_url}/user", headers=headers
            ) as response:
                if response.status == 401:
                    raise GitHubAuthError("GitHub access token is invalid or expired")
                elif response.status != 200:
                    error_text = await response.text()
                    raise GitHubAPIError(f"Failed to get user profile: {error_text}")

                profile_data = await response.json()

            logger.info(f"Retrieved GitHub user profile for: {profile_data.get('login')}")
            return GitHubUserProfile(**profile_data)

        except Exception as e:
            if isinstance(e, GitHubError):
                raise
            logger.error(f"Failed to get GitHub user profile: {str(e)}")
            raise GitHubError(f"Failed to get user profile: {str(e)}")

    async def get_user_repositories(
        self, access_token: str, per_page: int = 100, page: int = 1
    ) -> List[GitHubRepository]:
        """
        Get user's repositories from GitHub API.

        Args:
            access_token: Valid GitHub access token
            per_page: Number of repositories per page (max 100)
            page: Page number to retrieve

        Returns:
            List of GitHubRepository objects
        """
        try:
            session = await self.session
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Infrajet-Backend/1.0",
            }

            params = {
                "per_page": min(per_page, 100),
                "page": page,
                "sort": "updated",
                "direction": "desc",
            }

            async with session.get(
                f"{self.config.api_base_url}/user/repos",
                headers=headers,
                params=params,
            ) as response:
                if response.status == 401:
                    raise GitHubAuthError("GitHub access token is invalid or expired")
                elif response.status != 200:
                    error_text = await response.text()
                    raise GitHubAPIError(f"Failed to get repositories: {error_text}")

                repos_data = await response.json()

            repositories = [GitHubRepository(**repo) for repo in repos_data]
            logger.info(f"Retrieved {len(repositories)} repositories from GitHub")
            return repositories

        except Exception as e:
            if isinstance(e, GitHubError):
                raise
            logger.error(f"Failed to get GitHub repositories: {str(e)}")
            raise GitHubError(f"Failed to get repositories: {str(e)}")

    async def get_repository(
        self, access_token: str, owner: str, repo: str
    ) -> GitHubRepository:
        """
        Get a specific repository from GitHub API.

        Args:
            access_token: Valid GitHub access token
            owner: Repository owner username
            repo: Repository name

        Returns:
            GitHubRepository object
        """
        try:
            session = await self.session
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Infrajet-Backend/1.0",
            }

            async with session.get(
                f"{self.config.api_base_url}/repos/{owner}/{repo}",
                headers=headers,
            ) as response:
                if response.status == 401:
                    raise GitHubAuthError("GitHub access token is invalid or expired")
                elif response.status == 404:
                    raise RepositoryNotFoundError(f"Repository {owner}/{repo} not found")
                elif response.status != 200:
                    error_text = await response.text()
                    raise GitHubAPIError(f"Failed to get repository: {error_text}")

                repo_data = await response.json()

            logger.info(f"Retrieved repository: {owner}/{repo}")
            return GitHubRepository(**repo_data)

        except Exception as e:
            if isinstance(e, GitHubError):
                raise
            logger.error(f"Failed to get GitHub repository {owner}/{repo}: {str(e)}")
            raise GitHubError(f"Failed to get repository: {str(e)}")

    async def create_or_update_file(
        self,
        access_token: str,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str = "main",
        sha: Optional[str] = None,
    ) -> GitHubCommitResponse:
        """
        Create or update a file in a GitHub repository.

        Args:
            access_token: Valid GitHub access token
            owner: Repository owner username
            repo: Repository name
            path: File path in repository
            content: File content (will be base64 encoded)
            message: Commit message
            branch: Target branch (default: main)
            sha: SHA of existing file (for updates)

        Returns:
            GitHubCommitResponse with commit information
        """
        try:
            import base64

            session = await self.session
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Infrajet-Backend/1.0",
            }

            # Encode content to base64
            encoded_content = base64.b64encode(content.encode()).decode()

            data = {
                "message": message,
                "content": encoded_content,
                "branch": branch,
            }

            if sha:
                data["sha"] = sha

            async with session.put(
                f"{self.config.api_base_url}/repos/{owner}/{repo}/contents/{path}",
                headers=headers,
                json=data,
            ) as response:
                if response.status == 401:
                    raise GitHubAuthError("GitHub access token is invalid or expired")
                elif response.status == 403:
                    raise InsufficientPermissionsError(
                        f"Insufficient permissions to write to {owner}/{repo}"
                    )
                elif response.status == 404:
                    raise RepositoryNotFoundError(f"Repository {owner}/{repo} not found")
                elif response.status not in [200, 201]:
                    error_text = await response.text()
                    raise GitHubAPIError(f"Failed to create/update file: {error_text}")

                result = await response.json()

            logger.info(f"Successfully created/updated file: {path} in {owner}/{repo}")
            return GitHubCommitResponse(**result["commit"])

        except Exception as e:
            if isinstance(e, GitHubError):
                raise
            logger.error(f"Failed to create/update file in GitHub: {str(e)}")
            raise GitHubError(f"Failed to create/update file: {str(e)}")

    async def get_file_content(
        self, access_token: str, owner: str, repo: str, path: str, ref: str = "main"
    ) -> GitHubFileContent:
        """
        Get file content from a GitHub repository.

        Args:
            access_token: Valid GitHub access token
            owner: Repository owner username
            repo: Repository name
            path: File path in repository
            ref: Git reference (branch, tag, or commit SHA)

        Returns:
            GitHubFileContent with file information
        """
        try:
            session = await self.session
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Infrajet-Backend/1.0",
            }

            params = {"ref": ref}

            async with session.get(
                f"{self.config.api_base_url}/repos/{owner}/{repo}/contents/{path}",
                headers=headers,
                params=params,
            ) as response:
                if response.status == 401:
                    raise GitHubAuthError("GitHub access token is invalid or expired")
                elif response.status == 404:
                    raise RepositoryNotFoundError(f"File {path} not found in {owner}/{repo}")
                elif response.status != 200:
                    error_text = await response.text()
                    raise GitHubAPIError(f"Failed to get file content: {error_text}")

                file_data = await response.json()

            logger.info(f"Retrieved file content: {path} from {owner}/{repo}")
            return GitHubFileContent(**file_data)

        except Exception as e:
            if isinstance(e, GitHubError):
                raise
            logger.error(f"Failed to get file content from GitHub: {str(e)}")
            raise GitHubError(f"Failed to get file content: {str(e)}")

    async def validate_token(self, access_token: str) -> bool:
        """
        Validate a GitHub access token.

        Args:
            access_token: GitHub access token to validate

        Returns:
            True if token is valid, False otherwise
        """
        try:
            session = await self.session
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Infrajet-Backend/1.0",
            }

            async with session.get(
                f"{self.config.api_base_url}/user", headers=headers
            ) as response:
                is_valid = response.status == 200
                if is_valid:
                    logger.info("GitHub token validation successful")
                else:
                    logger.warning(f"GitHub token validation failed: {response.status}")
                return is_valid

        except Exception as e:
            logger.error(f"GitHub token validation error: {str(e)}")
            return False

    async def revoke_token(self, access_token: str) -> bool:
        """
        Revoke a GitHub access token.

        Args:
            access_token: GitHub access token to revoke

        Returns:
            True if revocation was successful
        """
        try:
            session = await self.session
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Infrajet-Backend/1.0",
            }

            # GitHub doesn't have a standard token revocation endpoint
            # But we can delete the authorization
            async with session.delete(
                f"{self.config.api_base_url}/applications/{self.config.client_id}/grant",
                headers=headers,
            ) as response:
                success = response.status in [200, 204]
                if success:
                    logger.info("Successfully revoked GitHub token")
                else:
                    logger.warning(f"GitHub token revocation returned status: {response.status}")
                return success

        except Exception as e:
            logger.error(f"Failed to revoke GitHub token: {str(e)}")
            return False