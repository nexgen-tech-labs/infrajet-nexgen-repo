"""
Project-GitHub Integration Service

Handles linking projects to GitHub repositories and automatic syncing of generations.
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.project import Project, CodeGeneration
from app.models.user import GitHubConnection
from app.services.github_app_oauth_service import GitHubAppOAuthService
from app.services.azure_file_service import get_azure_file_service
from app.dependencies.auth import CurrentUser

from logconfig.logger import get_logger

logger = get_logger()


class ProjectGitHubService:
    """
    Service for managing project-GitHub repository integration.

    Handles:
    - Linking/unlinking projects to GitHub repos
    - Auto-syncing completed generations to linked repos
    - Manual push/pull operations
    """

    def __init__(self):
        """Initialize the service."""
        self.github_service = GitHubAppOAuthService()

    async def link_project_to_repo(
        self,
        db: AsyncSession,
        user: CurrentUser,
        project_id: str,
        repo_owner: str,
        repo_name: str,
        use_oauth_token: bool = False
    ) -> Dict[str, Any]:
        """
        Link a project to a GitHub repository.

        Args:
            db: Database session
            user: Current user
            project_id: Project ID
            repo_owner: GitHub repository owner
            repo_name: GitHub repository name
            use_oauth_token: Whether to use OAuth token for access

        Returns:
            Link operation result
        """
        try:
            # Get project
            result = await db.execute(
                select(Project).filter(
                    Project.id == project_id,
                    Project.user_id == user.supabase_user_id
                )
            )
            project = result.scalars().first()

            if not project:
                return {
                    "success": False,
                    "error": "Project not found"
                }

            # Get GitHub connection
            result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.supabase_user_id == user.supabase_user_id,
                    GitHubConnection.is_active == True
                )
            )
            github_conn = result.scalars().first()

            if not github_conn:
                logger.warning(f"No active GitHub connection found for user {user.supabase_user_id}")
                return {
                    "success": False,
                    "error": "GitHub account not connected. Please connect your GitHub account first.",
                    "action_required": "connect_github"
                }

            # Validate that we have the necessary tokens
            if not github_conn.github_access_token:
                logger.error(f"GitHub connection found but no access token for user {user.supabase_user_id}")
                return {
                    "success": False,
                    "error": "GitHub connection is incomplete. Please reconnect your GitHub account.",
                    "action_required": "reconnect_github"
                }

            # Get repository info from GitHub
            repo_info = await self._get_repo_info(
                github_conn, repo_owner, repo_name, use_oauth_token
            )

            if not repo_info:
                return {
                    "success": False,
                    "error": "Repository not found or not accessible"
                }

            # Link project to repository
            project.link_to_github(
                repo_id=repo_info["id"],
                repo_name=f"{repo_owner}/{repo_name}",
                installation_id=github_conn.github_installation_id
            )

            await db.commit()
            await db.refresh(project)

            logger.info(f"Linked project {project_id} to GitHub repo {repo_owner}/{repo_name}")

            return {
                "success": True,
                "message": f"Project linked to {repo_owner}/{repo_name}",
                "repository": {
                    "id": repo_info["id"],
                    "name": repo_info["name"],
                    "full_name": repo_info["full_name"],
                    "html_url": repo_info["html_url"],
                    "private": repo_info["private"]
                }
            }

        except Exception as e:
            logger.error(f"Error linking project {project_id} to repo: {str(e)}")
            await db.rollback()
            return {
                "success": False,
                "error": str(e)
            }

    async def unlink_project_from_repo(
        self,
        db: AsyncSession,
        user: CurrentUser,
        project_id: str
    ) -> Dict[str, Any]:
        """
        Unlink a project from its GitHub repository.

        Args:
            db: Database session
            user: Current user
            project_id: Project ID

        Returns:
            Unlink operation result
        """
        try:
            # Get project
            result = await db.execute(
                select(Project).filter(
                    Project.id == project_id,
                    Project.user_id == user.supabase_user_id
                )
            )
            project = result.scalars().first()

            if not project:
                return {
                    "success": False,
                    "error": "Project not found"
                }

            if not project.is_github_linked:
                return {
                    "success": False,
                    "error": "Project is not linked to GitHub"
                }

            # Unlink project
            project.unlink_from_github()
            await db.commit()

            logger.info(f"Unlinked project {project_id} from GitHub repo")

            return {
                "success": True,
                "message": "Project unlinked from GitHub repository"
            }

        except Exception as e:
            logger.error(f"Error unlinking project {project_id}: {str(e)}")
            await db.rollback()
            return {
                "success": False,
                "error": str(e)
            }

    async def sync_generation_to_repo(
        self,
        db: AsyncSession,
        generation_id: str
    ) -> Dict[str, Any]:
        """
        Sync a completed generation to its linked GitHub repository.

        Args:
            db: Database session
            generation_id: Generation ID

        Returns:
            Sync operation result
        """
        try:
            # Get generation with project
            result = await db.execute(
                select(CodeGeneration).filter(
                    CodeGeneration.id == generation_id
                ).options(
                    select(Project).joinedload(CodeGeneration.project)
                )
            )
            generation = result.scalars().first()

            if not generation:
                return {
                    "success": False,
                    "error": "Generation not found"
                }

            project = generation.project

            if not project.is_github_linked:
                return {
                    "success": False,
                    "error": "Project is not linked to GitHub repository"
                }

            # Get GitHub connection for project owner
            result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.supabase_user_id == project.user_id,
                    GitHubConnection.is_active == True
                )
            )
            github_conn = result.scalars().first()

            if not github_conn:
                logger.warning(f"No active GitHub connection found for project owner {project.user_id}")
                return {
                    "success": False,
                    "error": "Project owner has not connected their GitHub account. Auto-sync requires GitHub connection.",
                    "action_required": "connect_github"
                }

            # Validate that we have the necessary tokens
            if not github_conn.github_access_token:
                logger.error(f"GitHub connection found but no access token for project owner {project.user_id}")
                return {
                    "success": False,
                    "error": "Project owner's GitHub connection is incomplete. Auto-sync cannot proceed.",
                    "action_required": "reconnect_github"
                }

            # Get generation files from Azure
            azure_service = await get_azure_file_service()
            files = await azure_service.list_user_files(
                user_id=project.user_id,
                project_id=project.id,
                generation_id=generation.id
            )

            if not files:
                return {
                    "success": False,
                    "error": "No files found in generation"
                }

            # Prepare files for GitHub sync - organize under generation folder
            files_content = {}
            for file_info in files:
                content = await azure_service.get_file_content(
                    user_id=project.user_id,
                    project_id=project.id,
                    generation_id=generation.id,
                    file_path=file_info.relative_path
                )
                if content is not None:
                    # Always organize generation files under generation_id/ structure
                    generation_folder = generation.id
                    github_path = f"{generation_folder}/{file_info.relative_path}"
                    files_content[github_path] = content

            if not files_content:
                return {
                    "success": False,
                    "error": "Failed to read generation files"
                }

            # Determine token type based on repo ownership
            repo_owner, repo_name = project.github_repo_name.split("/", 1)
            use_oauth_token = await self._should_use_oauth_token(
                github_conn, repo_owner, repo_name
            )

            # Create a user-like object for the GitHub service
            from app.dependencies.auth import CurrentUser
            mock_user = type('MockUser', (), {
                'supabase_user_id': project.user_id,
                'id': 'system'  # Mock ID for logging
            })()

            # Sync to GitHub
            sync_result = await self.github_service.sync_files_to_repository(
                db=db,
                user=mock_user,
                repository_full_name=project.github_repo_name,
                files_content=files_content,
                commit_message=f"Auto-sync generation {generation.id[:8]}: {generation.query[:50]}...",
                use_oauth_token=use_oauth_token
            )

            if sync_result["success"]:
                # Update project's last sync timestamp
                project.update_github_sync()
                await db.commit()

                logger.info(f"Auto-synced generation {generation_id} to {project.github_repo_name}")

            return sync_result

        except Exception as e:
            logger.error(f"Error syncing generation {generation_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def push_project_files_to_repo(
        self,
        db: AsyncSession,
        user: CurrentUser,
        project_id: str,
        generation_id: Optional[str] = None,
        commit_message: str = "Manual sync from InfraJet",
        branch: str = "main"
    ) -> Dict[str, Any]:
        """
        Manually push project files to linked GitHub repository.

        Args:
            db: Database session
            user: Current user
            project_id: Project ID
            generation_id: Optional specific generation, or all generations
            commit_message: Commit message
            branch: Target branch

        Returns:
            Push operation result
        """
        try:
            # Get project
            result = await db.execute(
                select(Project).filter(
                    Project.id == project_id,
                    Project.user_id == user.supabase_user_id
                )
            )
            project = result.scalars().first()

            if not project or not project.is_github_linked:
                return {
                    "success": False,
                    "error": "Project not found or not linked to GitHub"
                }

            # Get all files for the project/generation
            azure_service = await get_azure_file_service()
            files = await azure_service.list_user_files(
                user_id=user.supabase_user_id,
                project_id=project_id,
                generation_id=generation_id
            )

            if not files:
                return {
                    "success": False,
                    "error": "No files found to push"
                }

            # Prepare files content - always organize under generation folders
            files_content = {}
            for file_info in files:
                content = await azure_service.get_file_content(
                    user_id=user.supabase_user_id,
                    project_id=project_id,
                    generation_id=file_info.generation_id or generation_id,
                    file_path=file_info.relative_path
                )
                if content is not None:
                    # Always organize files under generation_id/filename structure
                    if generation_id is not None:
                        # Specific generation requested - use that generation folder
                        generation_folder = generation_id
                    else:
                        # No specific generation - use file's generation folder
                        generation_folder = file_info.generation_id or "unknown_generation"

                    github_path = f"{generation_folder}/{file_info.relative_path}"
                    files_content[github_path] = content

            # Determine token type
            repo_owner, repo_name = project.github_repo_name.split("/", 1)
            use_oauth_token = await self._should_use_oauth_token_for_user(
                db, user, repo_owner, repo_name
            )

            # Push to GitHub
            sync_result = await self.github_service.sync_files_to_repository(
                db=db,
                user=user,
                repository_full_name=project.github_repo_name,
                files_content=files_content,
                commit_message=commit_message,
                branch=branch,
                use_oauth_token=use_oauth_token
            )

            if sync_result["success"]:
                project.update_github_sync()
                await db.commit()

            return sync_result

        except Exception as e:
            logger.error(f"Error pushing project files: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def pull_repo_to_project(
        self,
        db: AsyncSession,
        user: CurrentUser,
        project_id: str,
        repo_path: str = "",
        branch: str = "main"
    ) -> Dict[str, Any]:
        """
        Pull files from linked GitHub repository to project.

        Args:
            db: Database session
            user: Current user
            project_id: Project ID
            repo_path: Optional sub-path in repository
            branch: Branch to pull from

        Returns:
            Pull operation result
        """
        try:
            # Get project
            result = await db.execute(
                select(Project).filter(
                    Project.id == project_id,
                    Project.user_id == user.supabase_user_id
                )
            )
            project = result.scalars().first()

            if not project or not project.is_github_linked:
                return {
                    "success": False,
                    "error": "Project not found or not linked to GitHub"
                }

            # This would require implementing GitHub repository content fetching
            # For now, return not implemented
            return {
                "success": False,
                "error": "Pull functionality not yet implemented"
            }

        except Exception as e:
            logger.error(f"Error pulling repo to project: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_project_github_status(
        self,
        db: AsyncSession,
        user: CurrentUser,
        project_id: str
    ) -> Dict[str, Any]:
        """
        Get GitHub integration status for a project.

        Args:
            db: Database session
            user: Current user
            project_id: Project ID

        Returns:
            Project GitHub status
        """
        try:
            # Get project
            result = await db.execute(
                select(Project).filter(
                    Project.id == project_id,
                    Project.user_id == user.supabase_user_id
                )
            )
            project = result.scalars().first()

            if not project:
                return {
                    "success": False,
                    "error": "Project not found"
                }

            return {
                "success": True,
                "data": {
                    "project_id": project.id,
                    "github_linked": project.is_github_linked,
                    "github_repo_name": project.github_repo_name,
                    "github_repo_id": project.github_repo_id,
                    "github_installation_id": project.github_installation_id,
                    "last_github_sync": project.last_github_sync.isoformat() if project.last_github_sync else None
                }
            }

        except Exception as e:
            logger.error(f"Error getting project GitHub status: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _get_repo_info(
        self,
        github_conn: GitHubConnection,
        repo_owner: str,
        repo_name: str,
        use_oauth_token: bool
    ) -> Optional[Dict[str, Any]]:
        """Get repository information from GitHub."""
        try:
            # This would need to be implemented in GitHubAppOAuthService
            # For now, return mock data
            return {
                "id": 12345,
                "name": repo_name,
                "full_name": f"{repo_owner}/{repo_name}",
                "html_url": f"https://github.com/{repo_owner}/{repo_name}",
                "private": False
            }
        except Exception:
            return None

    async def _should_use_oauth_token(
        self,
        github_conn: GitHubConnection,
        repo_owner: str,
        repo_name: str
    ) -> bool:
        """Determine if OAuth token should be used for a repository."""
        # Simple logic: use OAuth for personal repos, installation for org repos
        return repo_owner == github_conn.github_username

    async def _should_use_oauth_token_for_user(
        self,
        db: AsyncSession,
        user: CurrentUser,
        repo_owner: str,
        repo_name: str
    ) -> bool:
        """Determine token type for a user's repository access."""
        # Get user's GitHub connection
        result = await db.execute(
            select(GitHubConnection).filter(
                GitHubConnection.supabase_user_id == user.supabase_user_id,
                GitHubConnection.is_active == True
            )
        )
        github_conn = result.scalars().first()

        if github_conn:
            return repo_owner == github_conn.github_username

        return False

    async def create_project_branch(
        self,
        db: AsyncSession,
        user: CurrentUser,
        project_id: str,
        new_branch_name: str,
        source_branch: str = "main"
    ) -> Dict[str, Any]:
        """
        Create a new branch in a project's linked GitHub repository.

        Args:
            db: Database session
            user: Current user
            project_id: Project ID
            new_branch_name: Name of the new branch to create
            source_branch: Source branch to create from (default: "main")

        Returns:
            Branch creation result
        """
        try:
            # Validate branch name
            if not new_branch_name or not new_branch_name.strip():
                return {
                    "success": False,
                    "error": "Branch name is required and cannot be empty"
                }

            # GitHub branch name validation (basic)
            if any(char in new_branch_name for char in [' ', '..', '~', '^', ':', '\\', '?', '[', ']', '*']):
                return {
                    "success": False,
                    "error": "Branch name contains invalid characters"
                }

            if len(new_branch_name) > 255:
                return {
                    "success": False,
                    "error": "Branch name is too long (maximum 255 characters)"
                }

            # Get project
            result = await db.execute(
                select(Project).filter(
                    Project.id == project_id,
                    Project.user_id == user.supabase_user_id
                )
            )
            project = result.scalars().first()

            if not project:
                return {
                    "success": False,
                    "error": "Project not found"
                }

            if not project.is_github_linked:
                return {
                    "success": False,
                    "error": "Project is not linked to GitHub repository"
                }

            # Determine token type
            repo_owner, repo_name = project.github_repo_name.split("/", 1)
            use_oauth_token = await self._should_use_oauth_token_for_user(
                db, user, repo_owner, repo_name
            )

            # Create branch
            result = await self.github_service.create_branch(
                db=db,
                user=user,
                repository_full_name=project.github_repo_name,
                new_branch_name=new_branch_name.strip(),
                source_branch=source_branch,
                use_oauth_token=use_oauth_token
            )

            return result

        except Exception as e:
            logger.error(f"Error creating branch '{new_branch_name}' for project {project_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_project_repository_branches(
        self,
        db: AsyncSession,
        user: CurrentUser,
        project_id: str
    ) -> Dict[str, Any]:
        """
        Get branches for a project's linked GitHub repository.

        Args:
            db: Database session
            user: Current user
            project_id: Project ID

        Returns:
            Branches information
        """
        try:
            # Get project
            result = await db.execute(
                select(Project).filter(
                    Project.id == project_id,
                    Project.user_id == user.supabase_user_id
                )
            )
            project = result.scalars().first()

            if not project:
                return {
                    "success": False,
                    "error": "Project not found"
                }

            if not project.is_github_linked:
                return {
                    "success": False,
                    "error": "Project is not linked to GitHub repository"
                }

            # Determine token type
            repo_owner, repo_name = project.github_repo_name.split("/", 1)
            use_oauth_token = await self._should_use_oauth_token_for_user(
                db, user, repo_owner, repo_name
            )

            # Get branches
            branches = await self.github_service.get_repository_branches(
                db=db,
                user=user,
                repository_full_name=project.github_repo_name,
                use_oauth_token=use_oauth_token
            )

            return {
                "success": True,
                "data": {
                    "repository": project.github_repo_name,
                    "branches": branches,
                    "total_branches": len(branches)
                }
            }

        except Exception as e:
            logger.error(f"Error getting repository branches for project {project_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }