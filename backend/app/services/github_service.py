"""
GitHub OAuth integration service.

This service handles GitHub OAuth2 authentication flow, token management,
repository operations, and synchronization functionality.
"""

import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from cryptography.fernet import Fernet
import base64
import os

from logconfig.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.github import (
    GitHubConfig,
    GitHubService as CoreGitHubService,
    GitHubTokenResponse,
    GitHubUserProfile,
    GitHubRepository,
    GitHubCommitResponse,
    GitHubError,
    GitHubAuthError,
    GitHubAPIError,
    RepositoryNotFoundError,
    InsufficientPermissionsError,
)
from app.core.settings import get_settings
from app.models.user import User, GitHubConnection, GitHubSyncRecord, GitHubSyncStatus
from app.schemas.github import (
    GitHubConnectionStatus,
    GitHubSyncResponse,
    GitHubSyncHistory,
    GitHubSyncStatus as SchemaSyncStatus,
)

logger = get_logger()
settings = get_settings()


class GitHubIntegrationService:
    """
    Service for handling GitHub OAuth integration and repository operations.

    This service bridges the GitHub OAuth2 flow with the application's
    user management system, handling user authentication, token management,
    and repository synchronization.
    """

    def __init__(self):
        """Initialize the GitHub integration service."""
        self.github_config = settings.get_github_config()
        self.github_service = CoreGitHubService(self.github_config)
        self._encryption_key = self._get_or_create_encryption_key()

    def _get_or_create_encryption_key(self) -> bytes:
        """
        Get or create encryption key for token storage.

        Returns:
            Encryption key bytes
        """
        # In production, this should be stored securely (e.g., in environment variables or key vault)
        key_env = os.getenv("GITHUB_TOKEN_ENCRYPTION_KEY")
        if key_env:
            return base64.urlsafe_b64decode(key_env.encode())
        
        # For development, generate a key (this should be persistent in production)
        key = Fernet.generate_key()
        logger.warning(
            "Generated new encryption key for GitHub tokens. "
            "In production, set GITHUB_TOKEN_ENCRYPTION_KEY environment variable."
        )
        return key

    def _encrypt_token(self, token: str) -> str:
        """
        Encrypt a token for secure storage.

        Args:
            token: Token to encrypt

        Returns:
            Encrypted token string
        """
        if not token:
            return ""
        
        fernet = Fernet(self._encryption_key)
        encrypted_token = fernet.encrypt(token.encode())
        return base64.urlsafe_b64encode(encrypted_token).decode()

    def _decrypt_token(self, encrypted_token: str) -> str:
        """
        Decrypt a token from storage.

        Args:
            encrypted_token: Encrypted token string

        Returns:
            Decrypted token string
        """
        if not encrypted_token:
            return ""
        
        try:
            fernet = Fernet(self._encryption_key)
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_token.encode())
            decrypted_token = fernet.decrypt(encrypted_bytes)
            return decrypted_token.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt GitHub token: {str(e)}")
            return ""

    async def get_authorization_url(self, state: Optional[str] = None) -> Tuple[str, str]:
        """
        Generate GitHub authorization URL for OAuth2 flow.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Tuple of (authorization_url, state)
        """
        if state is None:
            state = secrets.token_urlsafe(32)

        try:
            auth_url = await self.github_service.get_authorization_url(state)
            logger.info(f"Generated GitHub authorization URL for state: {state}")
            return auth_url, state
        except Exception as e:
            logger.error(f"Failed to generate GitHub authorization URL: {str(e)}")
            raise GitHubError(f"Failed to generate authorization URL: {str(e)}")

    async def exchange_code_for_token(
        self, db: AsyncSession, user: User, code: str
    ) -> GitHubUserProfile:
        """
        Exchange authorization code for access token and connect GitHub account.

        Args:
            db: Database session
            user: User object to connect GitHub account to
            code: Authorization code from GitHub callback

        Returns:
            GitHubUserProfile with user information
        """
        logger.info(f"Exchanging GitHub code for token for user: {user.id}")

        try:
            # Exchange code for token
            token_response = await self.github_service.exchange_code_for_token(code)
            
            # Get user profile from GitHub
            github_profile = await self.github_service.get_user_profile(
                token_response.access_token
            )

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

            # Store encrypted token in GitHub connections table
            encrypted_token = self._encrypt_token(token_response.access_token)
            github_connection.connect_github_oauth(
                github_user_id=github_profile.id,
                github_username=github_profile.login,
                github_email=getattr(github_profile, 'email', None),
                access_token=encrypted_token,
                token_expires_at=None  # GitHub OAuth tokens don't have expiration
            )

            await db.commit()
            await db.refresh(user)
            await db.refresh(github_connection)

            logger.info(f"Successfully connected GitHub OAuth account for user: {user.id}")
            return github_profile

        except Exception as e:
            logger.error(
                f"Error exchanging GitHub code for user {user.id}: {str(e)}",
                exc_info=True,
            )
            await db.rollback()
            raise

    async def get_user_repositories(
        self, db: AsyncSession, user: User, page: int = 1, per_page: int = 30
    ) -> List[GitHubRepository]:
        """
        Get user's GitHub repositories.

        Args:
            db: Database session
            user: User object
            page: Page number
            per_page: Items per page

        Returns:
            List of GitHubRepository objects
        """
        # Get GitHub connection for this user
        result = await db.execute(
            select(GitHubConnection).filter(
                GitHubConnection.supabase_user_id == user.supabase_user_id,
                GitHubConnection.is_github_oauth_connected == True
            )
        )
        github_connection = result.scalars().first()

        if not github_connection:
            raise GitHubError("GitHub account not connected")

        try:
            # Decrypt access token
            access_token = self._decrypt_token(github_connection.github_access_token or "")
            if not access_token:
                raise GitHubError("GitHub access token not available")

            # Get repositories from GitHub
            repositories = await self.github_service.get_user_repositories(
                access_token, per_page=per_page, page=page
            )

            logger.info(f"Retrieved {len(repositories)} repositories for user: {user.id}")
            return repositories

        except Exception as e:
            logger.error(
                f"Error getting repositories for user {user.id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def get_repository(
        self, db: AsyncSession, user: User, owner: str, repo: str
    ) -> GitHubRepository:
        """
        Get a specific repository.

        Args:
            db: Database session
            user: User object
            owner: Repository owner
            repo: Repository name

        Returns:
            GitHubRepository object
        """
        if not user.is_github_connected:
            raise GitHubError("GitHub account not connected")

        try:
            # Decrypt access token
            access_token = self._decrypt_token(user.github_access_token or "")
            if not access_token:
                raise GitHubError("GitHub access token not available")

            # Get repository from GitHub
            repository = await self.github_service.get_repository(
                access_token, owner, repo
            )

            logger.info(f"Retrieved repository {owner}/{repo} for user: {user.id}")
            return repository

        except Exception as e:
            logger.error(
                f"Error getting repository {owner}/{repo} for user {user.id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def sync_project_to_repository(
        self,
        db: AsyncSession,
        user: User,
        project_id: str,
        repository_full_name: str,
        files_content: Dict[str, str],
        commit_message: str,
        branch: str = "main",
    ) -> GitHubSyncResponse:
        """
        Sync project files to a GitHub repository with enhanced conflict detection and retry logic.

        Args:
            db: Database session
            user: User object
            project_id: Project ID to sync
            repository_full_name: Target repository (owner/repo)
            files_content: Dictionary of file paths to content
            commit_message: Commit message
            branch: Target branch

        Returns:
            GitHubSyncResponse with sync results
        """
        if not user.is_github_connected:
            raise GitHubError("GitHub account not connected")

        logger.info(
            f"Starting enhanced sync of project {project_id} to {repository_full_name} for user: {user.id}"
        )

        try:
            # Decrypt access token
            access_token = self._decrypt_token(user.github_access_token or "")
            if not access_token:
                raise GitHubError("GitHub access token not available")

            # Parse repository name
            owner, repo = repository_full_name.split("/", 1)

            # Create or update sync record
            result = await db.execute(
                select(GitHubSyncRecord).filter(
                    GitHubSyncRecord.project_id == project_id,
                    GitHubSyncRecord.github_repository == repository_full_name,
                    GitHubSyncRecord.user_id == user.id,
                )
            )
            sync_record = result.scalars().first()

            if not sync_record:
                sync_record = GitHubSyncRecord(
                    project_id=project_id,
                    user_id=user.id,
                    github_repository=repository_full_name,
                    sync_status=GitHubSyncStatus.IN_PROGRESS,
                )
                db.add(sync_record)
            else:
                sync_record.sync_status = GitHubSyncStatus.IN_PROGRESS
                sync_record.sync_errors = None

            await db.commit()

            # Enhanced sync with conflict detection and retry logic
            sync_result = await self._sync_files_with_conflict_detection(
                access_token=access_token,
                owner=owner,
                repo=repo,
                branch=branch,
                files_content=files_content,
                commit_message=commit_message,
                sync_record=sync_record
            )

            # Update sync record with results
            if sync_result["errors"]:
                sync_record.sync_status = GitHubSyncStatus.FAILED
                sync_record.sync_errors = "; ".join(sync_result["errors"])
            else:
                sync_record.sync_status = GitHubSyncStatus.COMPLETED
                sync_record.last_sync_at = datetime.utcnow()
                if sync_result["commit_shas"]:
                    sync_record.last_commit_sha = sync_result["commit_shas"][-1]

            await db.commit()
            await db.refresh(sync_record)

            # Create response
            sync_response = GitHubSyncResponse(
                sync_id=str(sync_record.id),
                status=SchemaSyncStatus(sync_record.sync_status.value),
                repository_full_name=repository_full_name,
                branch=branch,
                commit_sha=sync_record.last_commit_sha,
                commit_url=(
                    f"https://github.com/{repository_full_name}/commit/{sync_record.last_commit_sha}"
                    if sync_record.last_commit_sha
                    else None
                ),
                files_synced=sync_result["files_synced"],
                error_message=sync_record.sync_errors,
                created_at=sync_record.created_at,
                completed_at=sync_record.last_sync_at,
            )

            logger.info(
                f"Completed enhanced sync of project {project_id}: {sync_result['files_synced']} files synced, {len(sync_result['errors'])} errors"
            )
            return sync_response

        except Exception as e:
            # Update sync record with error
            if 'sync_record' in locals():
                sync_record.sync_status = GitHubSyncStatus.FAILED
                sync_record.sync_errors = str(e)
                await db.commit()

            logger.error(
                f"Error syncing project {project_id} for user {user.id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def get_sync_history(
        self, db: AsyncSession, user: User, project_id: str
    ) -> GitHubSyncHistory:
        """
        Get sync history for a project.

        Args:
            db: Database session
            user: User object
            project_id: Project ID

        Returns:
            GitHubSyncHistory with sync records
        """
        try:
            # Get sync records for the project
            result = await db.execute(
                select(GitHubSyncRecord)
                .filter(
                    GitHubSyncRecord.project_id == project_id,
                    GitHubSyncRecord.user_id == user.id,
                )
                .order_by(GitHubSyncRecord.created_at.desc())
            )
            sync_records = result.scalars().all()

            if not sync_records:
                # Return empty history
                return GitHubSyncHistory(
                    project_id=project_id,
                    repository_full_name="",
                    sync_records=[],
                    total_syncs=0,
                    last_successful_sync=None,
                    current_status=SchemaSyncStatus.PENDING,
                )

            # Find last successful sync
            last_successful_sync = None
            for record in sync_records:
                if record.sync_status == GitHubSyncStatus.COMPLETED and record.last_sync_at:
                    last_successful_sync = record.last_sync_at
                    break

            # Get current status (most recent record)
            current_status = SchemaSyncStatus(sync_records[0].sync_status.value)

            return GitHubSyncHistory(
                project_id=project_id,
                repository_full_name=sync_records[0].github_repository,
                sync_records=[
                    GitHubSyncRecord(
                        id=record.id,
                        project_id=record.project_id,
                        user_id=record.user_id,
                        github_repository=record.github_repository,
                        last_sync_at=record.last_sync_at,
                        sync_status=SchemaSyncStatus(record.sync_status.value),
                        last_commit_sha=record.last_commit_sha,
                        sync_errors=record.sync_errors,
                        created_at=record.created_at,
                        updated_at=record.updated_at,
                    )
                    for record in sync_records
                ],
                total_syncs=len(sync_records),
                last_successful_sync=last_successful_sync,
                current_status=current_status,
            )

        except Exception as e:
            logger.error(
                f"Error getting sync history for project {project_id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def get_connection_status(
        self, db: AsyncSession, user: User
    ) -> GitHubConnectionStatus:
        """
        Get GitHub connection status for user.

        Args:
            db: Database session
            user: User object

        Returns:
            GitHubConnectionStatus with connection information
        """
        try:
            # Get GitHub connection for this user
            result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.supabase_user_id == user.supabase_user_id,
                    GitHubConnection.is_github_oauth_connected == True
                )
            )
            github_connection = result.scalars().first()

            if not github_connection:
                return GitHubConnectionStatus(
                    connected=False,
                    username=None,
                    connected_at=None,
                    repositories_count=None,
                    permissions=None,
                )

            # Try to validate token and get repository count
            repositories_count = None
            permissions = None

            try:
                access_token = self._decrypt_token(github_connection.github_access_token or "")
                if access_token:
                    # Validate token by getting user profile
                    is_valid = await self.github_service.validate_token(access_token)
                    if is_valid:
                        # Get repository count (first page to estimate)
                        repos = await self.github_service.get_user_repositories(
                            access_token, per_page=1, page=1
                        )
                        # This is just an estimate - GitHub API doesn't provide total count easily
                        repositories_count = len(repos) if repos else 0
                        permissions = ["repo", "user:email"]  # Based on our scopes
            except Exception:
                # Token might be invalid, but we still show as connected
                pass

            return GitHubConnectionStatus(
                connected=True,
                username=github_connection.github_username,
                connected_at=github_connection.github_connected_at,
                repositories_count=repositories_count,
                permissions=permissions,
            )

        except Exception as e:
            logger.error(
                f"Error getting GitHub connection status for user {user.id}: {str(e)}",
                exc_info=True,
            )
            raise

    async def disconnect_github(
        self, db: AsyncSession, user: User, revoke_token: bool = True
    ) -> bool:
        """
        Disconnect GitHub account from user.

        Args:
            db: Database session
            user: User object
            revoke_token: Whether to revoke the GitHub token

        Returns:
            True if disconnection was successful
        """
        logger.info(f"Disconnecting GitHub account for user: {user.id}")

        try:
            # Get GitHub connection for this user
            result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.supabase_user_id == user.supabase_user_id,
                    GitHubConnection.is_github_oauth_connected == True
                )
            )
            github_connection = result.scalars().first()

            if github_connection:
                # Revoke token if requested and possible
                if revoke_token and github_connection.github_access_token:
                    try:
                        access_token = self._decrypt_token(github_connection.github_access_token)
                        if access_token:
                            await self.github_service.revoke_token(access_token)
                            logger.info(f"Revoked GitHub token for user: {user.id}")
                    except Exception as revoke_error:
                        logger.warning(
                            f"Failed to revoke GitHub token for user {user.id}: {str(revoke_error)}"
                        )

                # Disconnect GitHub account
                github_connection.disconnect_github_oauth()
                await db.commit()
                logger.info(f"Successfully disconnected GitHub account for user: {user.id}")
                return True
            else:
                logger.warning(f"No GitHub connection found for user: {user.id}")
                return False

        except Exception as e:
            logger.error(
                f"Error disconnecting GitHub account for user {user.id}: {str(e)}",
                exc_info=True,
            )
            await db.rollback()
            return False

    async def validate_user_token(self, db: AsyncSession, user: User) -> bool:
        """
        Validate user's GitHub token.

        Args:
            db: Database session
            user: User object

        Returns:
            True if token is valid, False otherwise
        """
        # Get GitHub connection for this user
        result = await db.execute(
            select(GitHubConnection).filter(
                GitHubConnection.supabase_user_id == user.supabase_user_id,
                GitHubConnection.is_github_oauth_connected == True
            )
        )
        github_connection = result.scalars().first()

        if not github_connection:
            return False

        try:
            access_token = self._decrypt_token(github_connection.github_access_token or "")
            if not access_token:
                return False

            is_valid = await self.github_service.validate_token(access_token)

            if not is_valid:
                logger.warning(f"GitHub token invalid for user: {user.id}")
                # Optionally disconnect the account if token is invalid
                # github_connection.disconnect_github_oauth()
                # await db.commit()

            return is_valid

        except Exception as e:
            logger.error(
                f"Error validating GitHub token for user {user.id}: {str(e)}",
                exc_info=True,
            )
            return False

    async def refresh_user_profile(
        self, db: AsyncSession, user: User
    ) -> Optional[GitHubUserProfile]:
        """
        Refresh user's GitHub profile information.

        Args:
            db: Database session
            user: User object

        Returns:
            Updated GitHubUserProfile or None if failed
        """
        # Get GitHub connection for this user
        result = await db.execute(
            select(GitHubConnection).filter(
                GitHubConnection.supabase_user_id == user.supabase_user_id,
                GitHubConnection.is_github_oauth_connected == True
            )
        )
        github_connection = result.scalars().first()

        if not github_connection:
            return None

        try:
            access_token = self._decrypt_token(github_connection.github_access_token or "")
            if not access_token:
                return None

            # Get updated profile from GitHub
            github_profile = await self.github_service.get_user_profile(access_token)

            # Update GitHub connection username if it changed
            if github_profile.login != github_connection.github_username:
                github_connection.github_username = github_profile.login
                await db.commit()
                await db.refresh(github_connection)
                logger.info(f"Updated GitHub username for user {user.id}: {github_profile.login}")

            return github_profile

        except Exception as e:
            logger.error(
                f"Error refreshing GitHub profile for user {user.id}: {str(e)}",
                exc_info=True,
            )
            return None

    async def _sync_files_with_conflict_detection(
        self,
        access_token: str,
        owner: str,
        repo: str,
        branch: str,
        files_content: Dict[str, str],
        commit_message: str,
        sync_record: GitHubSyncRecord,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Sync files with enhanced conflict detection and retry logic.

        Args:
            access_token: GitHub access token
            owner: Repository owner
            repo: Repository name
            branch: Target branch
            files_content: Dictionary of file paths to content
            commit_message: Base commit message
            sync_record: Sync record for tracking
            max_retries: Maximum retry attempts per file

        Returns:
            Dictionary with sync results
        """
        commit_shas = []
        files_synced = 0
        errors = []
        conflicts_detected = []

        # Generate descriptive commit message with metadata
        enhanced_commit_message = self._generate_commit_message(
            base_message=commit_message,
            project_id=sync_record.project_id,
            file_count=len(files_content)
        )

        for file_path, content in files_content.items():
            retry_count = 0
            file_synced = False

            while retry_count < max_retries and not file_synced:
                try:
                    # Detect conflicts before syncing
                    conflict_info = await self._detect_file_conflicts(
                        access_token, owner, repo, file_path, content, branch
                    )

                    if conflict_info["has_conflict"]:
                        conflicts_detected.append(conflict_info)
                        
                        # Apply conflict resolution strategy
                        resolved_content, resolution_strategy = await self._resolve_file_conflict(
                            conflict_info, content, file_path
                        )
                        
                        if resolved_content is None:
                            errors.append(
                                f"Unresolvable conflict in {file_path}: {conflict_info['conflict_reason']}"
                            )
                            break

                        # Use resolved content
                        final_content = resolved_content
                        final_message = f"{enhanced_commit_message} - {file_path} (conflict resolved: {resolution_strategy})"
                    else:
                        final_content = content
                        final_message = f"{enhanced_commit_message} - {file_path}"

                    # Attempt to sync the file
                    commit_response = await self._sync_single_file_with_retry(
                        access_token=access_token,
                        owner=owner,
                        repo=repo,
                        file_path=file_path,
                        content=final_content,
                        message=final_message,
                        branch=branch,
                        existing_sha=conflict_info.get("existing_sha")
                    )

                    if commit_response:
                        commit_shas.append(commit_response.sha)
                        files_synced += 1
                        file_synced = True
                        logger.info(f"Successfully synced {file_path} (attempt {retry_count + 1})")
                    else:
                        retry_count += 1
                        if retry_count < max_retries:
                            logger.warning(f"Retrying sync for {file_path} (attempt {retry_count + 1})")
                            await asyncio.sleep(1 * retry_count)  # Exponential backoff

                except Exception as file_error:
                    retry_count += 1
                    error_msg = f"Failed to sync {file_path} (attempt {retry_count}): {str(file_error)}"
                    logger.error(error_msg)
                    
                    if retry_count >= max_retries:
                        errors.append(f"Failed to sync {file_path} after {max_retries} attempts: {str(file_error)}")
                    else:
                        await asyncio.sleep(1 * retry_count)  # Exponential backoff

        return {
            "commit_shas": commit_shas,
            "files_synced": files_synced,
            "errors": errors,
            "conflicts_detected": conflicts_detected
        }

    async def _detect_file_conflicts(
        self,
        access_token: str,
        owner: str,
        repo: str,
        file_path: str,
        new_content: str,
        branch: str
    ) -> Dict[str, Any]:
        """
        Detect potential conflicts before syncing a file.

        Args:
            access_token: GitHub access token
            owner: Repository owner
            repo: Repository name
            file_path: File path to check
            new_content: New content to sync
            branch: Target branch

        Returns:
            Dictionary with conflict information
        """
        try:
            # Try to get existing file
            existing_file = await self.github_service.get_file_content(
                access_token, owner, repo, file_path, branch
            )

            # Decode existing content
            import base64
            existing_content = base64.b64decode(existing_file.content or "").decode('utf-8')

            # Check for conflicts
            has_conflict = False
            conflict_reason = None

            # Content-based conflict detection
            if existing_content.strip() != new_content.strip():
                # Check if it's a simple addition/modification or a real conflict
                existing_lines = set(existing_content.splitlines())
                new_lines = set(new_content.splitlines())
                
                # If there are completely different lines, it might be a conflict
                if existing_lines - new_lines and new_lines - existing_lines:
                    has_conflict = True
                    conflict_reason = "Content differs significantly from existing file"

            return {
                "has_conflict": has_conflict,
                "conflict_reason": conflict_reason,
                "existing_sha": existing_file.sha,
                "existing_content": existing_content,
                "existing_size": existing_file.size,
                "file_path": file_path
            }

        except RepositoryNotFoundError:
            # File doesn't exist, no conflict
            return {
                "has_conflict": False,
                "conflict_reason": None,
                "existing_sha": None,
                "existing_content": None,
                "existing_size": 0,
                "file_path": file_path
            }
        except Exception as e:
            logger.warning(f"Could not check for conflicts in {file_path}: {str(e)}")
            return {
                "has_conflict": False,
                "conflict_reason": f"Could not check conflicts: {str(e)}",
                "existing_sha": None,
                "existing_content": None,
                "existing_size": 0,
                "file_path": file_path
            }

    async def _resolve_file_conflict(
        self,
        conflict_info: Dict[str, Any],
        new_content: str,
        file_path: str
    ) -> tuple[Optional[str], str]:
        """
        Resolve file conflicts using various strategies.

        Args:
            conflict_info: Conflict information
            new_content: New content to sync
            file_path: File path

        Returns:
            Tuple of (resolved_content, resolution_strategy)
        """
        existing_content = conflict_info.get("existing_content", "")
        
        # Strategy 1: For infrastructure files, prefer new content (overwrite)
        if file_path.endswith(('.tf', '.tfvars', '.json', '.yaml', '.yml')):
            return new_content, "overwrite_infrastructure"
        
        # Strategy 2: For documentation files, try to merge
        if file_path.endswith(('.md', '.txt', '.rst')):
            # Simple merge strategy: append new content if different
            if new_content.strip() not in existing_content:
                merged_content = f"{existing_content}\n\n# Generated Content\n{new_content}"
                return merged_content, "append_documentation"
            else:
                return existing_content, "keep_existing_documentation"
        
        # Strategy 3: For configuration files, prefer new content but add comment
        if file_path.endswith(('.conf', '.cfg', '.ini', '.env')):
            commented_existing = "\n".join([f"# {line}" for line in existing_content.splitlines()])
            merged_content = f"# Previous configuration (commented out):\n{commented_existing}\n\n# New configuration:\n{new_content}"
            return merged_content, "preserve_old_config"
        
        # Default strategy: Overwrite with new content
        return new_content, "overwrite_default"

    async def _sync_single_file_with_retry(
        self,
        access_token: str,
        owner: str,
        repo: str,
        file_path: str,
        content: str,
        message: str,
        branch: str,
        existing_sha: Optional[str] = None
    ) -> Optional[GitHubCommitResponse]:
        """
        Sync a single file with retry logic for transient failures.

        Args:
            access_token: GitHub access token
            owner: Repository owner
            repo: Repository name
            file_path: File path
            content: File content
            message: Commit message
            branch: Target branch
            existing_sha: SHA of existing file (if any)

        Returns:
            GitHubCommitResponse if successful, None if failed
        """
        try:
            commit_response = await self.github_service.create_or_update_file(
                access_token=access_token,
                owner=owner,
                repo=repo,
                path=file_path,
                content=content,
                message=message,
                branch=branch,
                sha=existing_sha,
            )
            return commit_response

        except Exception as e:
            logger.error(f"Failed to sync file {file_path}: {str(e)}")
            return None

    def _generate_commit_message(
        self,
        base_message: str,
        project_id: str,
        file_count: int
    ) -> str:
        """
        Generate descriptive commit message with metadata.

        Args:
            base_message: Base commit message
            project_id: Project ID
            file_count: Number of files being synced

        Returns:
            Enhanced commit message
        """
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        if not base_message or base_message.strip() == "":
            base_message = "Infrastructure code sync"
        
        enhanced_message = f"{base_message}\n\nProject: {project_id}\nFiles: {file_count}\nSynced: {timestamp}\nSource: Infrajet Code Generation"
        
        return enhanced_message

    async def retry_failed_sync(
        self,
        db: AsyncSession,
        user: User,
        sync_record_id: int,
        max_retries: int = 3
    ) -> GitHubSyncResponse:
        """
        Retry a failed sync operation.

        Args:
            db: Database session
            user: User object
            sync_record_id: ID of the sync record to retry
            max_retries: Maximum retry attempts

        Returns:
            GitHubSyncResponse with retry results
        """
        # Get the sync record
        result = await db.execute(
            select(GitHubSyncRecord).filter(
                GitHubSyncRecord.id == sync_record_id,
                GitHubSyncRecord.user_id == user.id,
            )
        )
        sync_record = result.scalars().first()

        if not sync_record:
            raise GitHubError(f"Sync record {sync_record_id} not found")

        if sync_record.sync_status != GitHubSyncStatus.FAILED:
            raise GitHubError(f"Sync record {sync_record_id} is not in failed state")

        logger.info(f"Retrying failed sync for record {sync_record_id}")

        # Get project files to retry sync
        from app.services.projects.crud_service import ProjectCRUDService
        from app.services.azure.file_operations import get_file_operations_service
        
        project_crud = ProjectCRUDService(db)
        file_service = await get_file_operations_service()

        try:
            # Get project with files
            project = await project_crud.get_project(
                sync_record.project_id, user.id, include_files=True
            )

            # Download current project files
            files_content = {}
            for project_file in project.files:
                try:
                    download_result = await file_service.download_file(project_file.azure_path)
                    if download_result.success and hasattr(download_result, 'content'):
                        files_content[project_file.file_path] = download_result.content
                except Exception as e:
                    logger.warning(f"Could not download file {project_file.file_path}: {str(e)}")

            if not files_content:
                raise GitHubError("No files found to sync")

            # Retry the sync
            return await self.sync_project_to_repository(
                db=db,
                user=user,
                project_id=sync_record.project_id,
                repository_full_name=sync_record.github_repository,
                files_content=files_content,
                commit_message=f"Retry sync - {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}",
                branch="main"
            )

        except Exception as e:
            logger.error(f"Error retrying sync for record {sync_record_id}: {str(e)}")
            raise GitHubError(f"Retry failed: {str(e)}")

    async def get_sync_conflicts(
        self,
        db: AsyncSession,
        user: User,
        project_id: str,
        repository_full_name: str,
        branch: str = "main"
    ) -> List[Dict[str, Any]]:
        """
        Get potential sync conflicts for a project before syncing.

        Args:
            db: Database session
            user: User object
            project_id: Project ID to check
            repository_full_name: Target repository
            branch: Target branch

        Returns:
            List of potential conflicts
        """
        if not user.is_github_connected:
            raise GitHubError("GitHub account not connected")

        try:
            access_token = self._decrypt_token(user.github_access_token or "")
            if not access_token:
                raise GitHubError("GitHub access token not available")

            owner, repo = repository_full_name.split("/", 1)

            # Get project files
            from app.services.projects.crud_service import ProjectCRUDService
            from app.services.azure.file_operations import get_file_operations_service
            
            project_crud = ProjectCRUDService(db)
            file_service = await get_file_operations_service()

            project = await project_crud.get_project(project_id, user.id, include_files=True)
            
            conflicts = []
            for project_file in project.files:
                try:
                    # Download current file content
                    download_result = await file_service.download_file(project_file.azure_path)
                    if not download_result.success or not hasattr(download_result, 'content'):
                        continue

                    # Check for conflicts
                    conflict_info = await self._detect_file_conflicts(
                        access_token, owner, repo, project_file.file_path,
                        download_result.content, branch
                    )

                    if conflict_info["has_conflict"]:
                        conflicts.append(conflict_info)

                except Exception as e:
                    logger.warning(f"Could not check conflicts for {project_file.file_path}: {str(e)}")

            return conflicts

        except Exception as e:
            logger.error(f"Error checking sync conflicts: {str(e)}")
            raise GitHubError(f"Failed to check conflicts: {str(e)}")

    async def sync_project_files_from_azure(
        self,
        db: AsyncSession,
        user: User,
        project_id: str,
        repository_full_name: str,
        commit_message: Optional[str] = None,
        branch: str = "main"
    ) -> GitHubSyncResponse:
        """
        Sync all project files from Azure File Share to GitHub repository.

        Args:
            db: Database session
            user: User object
            project_id: Project ID to sync
            repository_full_name: Target repository
            commit_message: Optional commit message
            branch: Target branch

        Returns:
            GitHubSyncResponse with sync results
        """
        try:
            # Get project files from database
            from app.services.projects.crud_service import ProjectCRUDService
            from app.services.azure.file_operations import get_file_operations_service
            
            project_crud = ProjectCRUDService(db)
            file_service = await get_file_operations_service()

            project = await project_crud.get_project(project_id, user.id, include_files=True)
            
            if not project.files:
                raise GitHubError(f"No files found in project {project_id}")

            # Download all project files from Azure
            files_content = {}
            download_errors = []

            for project_file in project.files:
                try:
                    download_result = await file_service.download_file(project_file.azure_path)
                    if download_result.success and hasattr(download_result, 'content'):
                        files_content[project_file.file_path] = download_result.content
                    else:
                        download_errors.append(f"Failed to download {project_file.file_path}: {download_result.error}")
                except Exception as e:
                    download_errors.append(f"Error downloading {project_file.file_path}: {str(e)}")

            if not files_content:
                error_msg = f"No files could be downloaded from project {project_id}"
                if download_errors:
                    error_msg += f". Errors: {'; '.join(download_errors)}"
                raise GitHubError(error_msg)

            # Generate commit message if not provided
            if not commit_message:
                commit_message = f"Sync project '{project.name}' from Infrajet"

            # Sync files to GitHub
            return await self.sync_project_to_repository(
                db=db,
                user=user,
                project_id=project_id,
                repository_full_name=repository_full_name,
                files_content=files_content,
                commit_message=commit_message,
                branch=branch
            )

        except Exception as e:
            logger.error(f"Error syncing project files from Azure: {str(e)}")
            raise GitHubError(f"Failed to sync project files: {str(e)}")

    async def close(self):
        """Close the GitHub service session."""
        await self.github_service.close()